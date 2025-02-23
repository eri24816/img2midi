from collections import defaultdict
from attr import dataclass
import cv2
import numpy as np
import matplotlib.pyplot as plt

SHOW_PLOTS = False

# Pitch range for mapping vertical position to MIDI notes
# note_range = np.array([67, 79])  # Original MIDI note range
# note_range = np.array([-0.5, 0.5])  # Normalized range option 1 
PITCH_RANGE = np.array([-1, 1])  # Normalized range option 2

# Convert pitch range to frequencies
FREQUENCY_RANGE = 440 * np.power(2, (PITCH_RANGE-69)/12)

# Maximum height for analysis window
MAX_ANALYSIS_HEIGHT = 200

# Threshold for binary image conversion
BINARY_THRESHOLD = 200

def find_stroke_contours(grayscale_image):
    """Find contours of strokes in the image"""
    # Convert to binary image
    _, binary_image = cv2.threshold(grayscale_image, BINARY_THRESHOLD, 255, cv2.THRESH_BINARY_INV)

    # apply median blur to remove noise
    binary_image = cv2.medianBlur(binary_image, 3)


    # Smooth image to improve contour detection
    blurred_image = cv2.GaussianBlur(binary_image, (5, 5), 0)


    # Dilate to connect nearby regions
    kernel = np.ones((5, 5), np.uint8)
    dilated_image = cv2.dilate(blurred_image, kernel, iterations=1)

    # Close gaps in strokes
    closed_image = cv2.morphologyEx(dilated_image, cv2.MORPH_CLOSE, kernel)


    # Find contours
    contours, _ = cv2.findContours(closed_image, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    return contours, cv2.threshold(closed_image, 100, 255, cv2.THRESH_BINARY)[1]

def find_stroke_boundaries(image_slice, slice_width, y_offset, height):
    """Find top and bottom boundaries of a stroke in an image slice"""
    # Find edges using Laplacian
    edges = cv2.Laplacian(image_slice, cv2.CV_64F)
    edges = cv2.convertScaleAbs(edges)
    
    # Get edge positions
    edge_positions = np.where(edges > 0)
    
    # Initialize boundary arrays
    top_boundaries = np.zeros(shape=(slice_width,))
    bottom_boundaries = np.ones(shape=(slice_width,)) * height
    
    # Find highest and lowest edge for each x position
    for i in range(len(edge_positions[1])):
        x_pos = edge_positions[1][i]
        y_pos = edge_positions[0][i]
        top_boundaries[x_pos] = max(y_pos, top_boundaries[x_pos])
        bottom_boundaries[x_pos] = min(y_pos, bottom_boundaries[x_pos])
    
    # Fill in gaps
    top_boundaries[top_boundaries == 0] = np.max(top_boundaries)
    bottom_boundaries[bottom_boundaries == height] = np.min(bottom_boundaries)
    
    return y_offset + top_boundaries, y_offset + bottom_boundaries

def get_center_of_mass(binary_image:np.ndarray):
    """Get the center of mass of the binary image"""
    x_coord = np.arange(binary_image.shape[1]).reshape(1,-1).repeat(binary_image.shape[0], axis=0)
    y_coord = np.arange(binary_image.shape[0]).reshape(-1,1).repeat(binary_image.shape[1], axis=1)
    return np.sum(x_coord * binary_image) / np.sum(binary_image), np.sum(y_coord * binary_image) / np.sum(binary_image)

def get_largest_island(array:np.ndarray):
    """Get the largest island in the binary image"""
    num_islands, islands = cv2.connectedComponents(array)
    largest_island = np.argmax([np.sum(islands == i) for i in range(1,num_islands+1)]) + 1
    return islands == largest_island

def get_margin(image:np.ndarray, x:int, y:int)->int:
    """Get the margin around the point (x,y), which is the distance to the nearest zero pixel"""
    search_radius = 30
    margin_r = search_radius
    for x_search in range(x, max(0, x-search_radius), -1):
        if image[y, x_search] == 0:
            margin_r = abs(x - x_search)
            break
    margin_l = search_radius
    for x_search in range(x+1, min(image.shape[1], x+search_radius)):
        if image[y, x_search] == 0:
            margin_l = abs(x_search - x)
            break
    margin_x = margin_r + margin_l

    margin_u = search_radius
    for y_search in range(y, max(0, y-search_radius), -1):
        if image[y_search, x] == 0:
            margin_u = abs(y - y_search)
            break
    margin_d = search_radius
    for y_search in range(y+1, min(image.shape[0], y+search_radius)):
        if image[y_search, x] == 0:
            margin_d = abs(y_search - y)
            break
    margin_y = margin_u + margin_d
    return min(margin_x, margin_y)

def stroke_to_parameters(stroke, hsv_image:np.ndarray, binary_image:np.ndarray, raw_image:np.ndarray, hop = 3):
    """Convert a stroke to parameters"""
    # invert raw image
    raw_image = 255 - raw_image

    rect = cv2.boundingRect(stroke)
    left = rect[0]
    right = rect[0] + rect[2]
    top = 0
    bottom = hsv_image.shape[0]

    n = (right - left) // hop

    slices = []
    for i in range(n):
        slices.append((left + i * hop, left + (i + 1) * hop))



    @dataclass
    class Point:
        x: float = 0
        y: float = 0
        margin: int = 0
        density: float = 0
        hue: float = 0
        saturation: float = 0
        value: float = 0

    points: list[Point] = []

    for l, r in slices:
        point = Point()
        points.append(point)
        center_x, _ = get_center_of_mass(binary_image[top:bottom, l:r])
        if np.isnan(center_x):
            center_x = (r - l) / 2
        center_x += l
        largest_vertical_island = get_largest_island(binary_image[top:bottom, int(center_x):int(center_x)+1])
        center_y = np.sum(largest_vertical_island.flatten() * np.arange(top, bottom)) / np.sum(largest_vertical_island)
        if np.isnan(center_y):
            center_y = top + (bottom - top) / 2


        point.x = center_x
        point.y = center_y

        margin = get_margin(binary_image, int(center_x), int(center_y))
        point.margin = margin

        # get density. it is the mean of raw image pixels where binary image is 1 in the center_x slice
        bin_slice = binary_image[top:bottom, int(center_x)]
        raw_slice = raw_image[top:bottom, int(center_x)]
        point.density = np.sum(bin_slice.astype(np.float32) * raw_slice.astype(np.float32)) / (np.sum(bin_slice)+1e-6) / 255

        # get hue, saturation, value. it is the mean of hsv image pixels where binary image is 1 in the center_x slice
        hsv_slice = hsv_image[top:bottom, int(center_x)].astype(np.float32)
        raw_slice = raw_image[top:bottom, int(center_x)].astype(np.float32)
        point.hue = float(np.sum(raw_slice * hsv_slice[:,0]) / (np.sum(raw_slice)+1e-6))
        point.saturation = float(np.sum(raw_slice * hsv_slice[:,1]) / (np.sum(raw_slice)+1e-6))
        point.value = float(np.sum(raw_slice * hsv_slice[:,2]) / (np.sum(raw_slice)+1e-6))



    # # show image with all centers of mass
    # # Draw center of mass in red
    # colorize the binary image with the margin

    if SHOW_PLOTS:
        binary_image = cv2.cvtColor(binary_image, cv2.COLOR_GRAY2BGR)
        # to 8 bit
        binary_image = binary_image.astype(np.float32) / 255
        for point in points:
            cv2.circle(binary_image, (int(point.x), int(point.y)), int(point.margin//4), (150,120,0), -1)
            #  add hsv text
        cv2.imshow('binary_image', binary_image)
        cv2.waitKey(0)

    parameters: defaultdict[str, list] = defaultdict(list)
    for point in points:
        parameters['pitch'].append(point.y/hsv_image.shape[0] * (PITCH_RANGE[0]-PITCH_RANGE[1]) + PITCH_RANGE[1])
        parameters['intensity'].append(point.margin / 30)
        parameters['density'].append(point.density)
        parameters['hue'].append(point.hue/255)
        parameters['saturation'].append(point.saturation/255)
        parameters['value'].append(point.value/255)
        parameters['x_position'].append(point.x)

    return parameters


@dataclass
class StrokeInfo:
    length: int
    parameters: dict[str, list]

def notation_to_parameters(image_input) -> list[StrokeInfo]:
    """
    Converts an image of musical notation into various parameters for sound synthesis.
    
    This function processes an image through several steps:
    1. Image preprocessing - resizes and adds borders
    2. Contour detection - finds the strokes/marks in the image 
    3. Parameter extraction - analyzes each stroke from left to right
    
    Args:
        image_input (str or bytes): Either a path to the input image file,
            or bytes containing the image data
        
    Returns:
        dict: Contains parameters extracted from the image:
            - intensity: List of intensity values for each stroke
            - pitch: List of MIDI note values for each stroke
            - density: List of density values for each stroke
            - hue: List of hue values for each stroke
            - saturation: List of saturation values for each stroke
            - value: List of brightness values for each stroke
            - x_position: List of x-coordinates for each measurement point
    """
    # Load image from either file path or bytes
    if isinstance(image_input, str):
        image = cv2.imread(image_input)
    else:
        # Convert bytes to numpy array
        nparr = np.frombuffer(image_input, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    
    if image is None:
        raise ValueError("Failed to load image")

    # Load and preprocess image
    image = cv2.resize(image, (image.shape[1]//4, image.shape[0]//4))
    border_size = round(image.shape[0] / 2)
    
    # Add white borders to give space for stroke analysis
    image = cv2.copyMakeBorder(
        image,
        top=border_size,
        bottom=border_size,
        left=0,
        right=0,
        borderType=cv2.BORDER_CONSTANT,
        value=(255, 255, 255)
    )
    
    # Convert to different color spaces for analysis
    grayscale_image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    hsv_image = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

    # Find strokes in the image
    strokes, binary_image = find_stroke_contours(grayscale_image)

    
    # For visualization if SHOW_PLOTS=True
    visualization_image = image.copy()
    cv2.drawContours(visualization_image, strokes, -1, (0, 255, 0), 2)
    

    assert len(strokes) > 0, "No strokes found in the image"

    
    stroke_info_list: list[StrokeInfo] = []

    # Process each stroke
    for stroke in strokes:
        parameters = stroke_to_parameters(stroke, hsv_image, binary_image, grayscale_image)

        stroke_info_list.append(StrokeInfo(len(parameters['x_position']), parameters))
    

    # Visualization code
    if SHOW_PLOTS:
        plt.imshow(visualization_image)
        plt.title("Detected Strokes")
        plt.axis('off')
        plt.show()
        
        plt.figure(figsize=(14, 8))
        for i, stroke_info in enumerate(stroke_info_list):
            parameters = stroke_info.parameters
            plt.subplot(3, 2, 1)
            plt.plot(parameters['x_position'], parameters['pitch'], label=f'Stroke {i+1} pitch')
            plt.title("Pitch (MIDI note)")
            plt.legend()
            
            plt.subplot(3, 2, 3)
            plt.plot(parameters['x_position'], parameters['intensity'], label=f'Stroke {i+1} width')
            plt.title("Width (intensity)")
            
            plt.subplot(3, 2, 5)
            plt.plot(parameters['x_position'], parameters['density'], label=f'Stroke {i+1} density')
            plt.title("Density")
            
            plt.subplot(3, 2, 2)
            plt.plot(parameters['x_position'], parameters['hue'], label=f'Stroke {i+1} hue')
            plt.title("Hue")
            
            plt.subplot(3, 2, 4)
            plt.plot(parameters['x_position'], parameters['saturation'], label=f'Stroke {i+1} saturation')
            plt.title("Saturation")
            
            plt.subplot(3, 2, 6)
            plt.plot(parameters['x_position'], parameters['value'], label=f'Stroke {i+1} value')
            plt.xlabel("Position")
            plt.title("Value")

        plt.tight_layout()
        plt.show()


    # # Normalize x positions
    # for i in range(len(x_positions)):
    #     x_positions[i] = (np.array(x_positions[i]) / image_width)
    # x_positions = np.array(x_positions)

    # print(stroke_intensities)
    
    # result = {
    #     'intensity': stroke_intensities,
    #     'pitch': stroke_pitches,
    #     'density': stroke_densities,
    #     'hue': stroke_hues,
    #     'saturation': stroke_saturations,
    #     'value': stroke_values,
    #     'x_position': x_positions
    # }

    return stroke_info_list
