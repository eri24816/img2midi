from collections import defaultdict
from dataclasses import dataclass, field
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
    # blurred_image = cv2.GaussianBlur(binary_image, (3, 3), 0)
    blurred_image = binary_image


    # Dilate to connect nearby regions
    kernel = np.ones((3, 3), np.uint8)
    dilated_image = cv2.dilate(blurred_image, kernel, iterations=1)
    # dilated_image = blurred_image

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
    try:
        num_islands, islands = cv2.connectedComponents(array)
    except Exception as e:
        print(array.shape)
        raise e
    largest_island = np.argmax([np.sum(islands == i) for i in range(1,num_islands+1)]) + 1
    return islands == largest_island

def get_margin(image:np.ndarray, x:int, y:int)->tuple[int, dict[str, int]]:
    """Get the margin around the point (x,y), which is the distance to the nearest zero pixel"""
    search_radius = 30

    margin_l = 0
    margin_r = 0
    margin_u = 0
    margin_d = 0

    for x_search in range(x, max(0, x-search_radius), -1):
        if image[y, x_search] == 0:
            margin_l = abs(x - x_search) - 1
            break
        else:
            margin_l = abs(x - x_search)

    for x_search in range(x+1, min(image.shape[1], x+search_radius)):
        if image[y, x_search] == 0:
            margin_r = abs(x_search - x) - 1
            break
        else:
            margin_r = abs(x_search - x)

    margin_u = search_radius
    for y_search in range(y, max(0, y-search_radius), -1):
        if image[y_search, x] == 0:
            margin_u = abs(y - y_search) - 1
            break
        else:
            margin_u = abs(y - y_search)

    for y_search in range(y+1, min(image.shape[0], y+search_radius)):
        if image[y_search, x] == 0:
            margin_d = abs(y_search - y) - 1
            break
        else:
            margin_d = abs(y_search - y)

    margin_x = margin_r + margin_l
    margin_y = margin_u + margin_d
    return min(margin_x, margin_y), {'r':margin_r, 'l':margin_l, 'u':margin_u, 'd':margin_d}

def stroke_to_parameters(stroke, hsv_image:np.ndarray, binary_image:np.ndarray, raw_image:np.ndarray, x_shift: float, y_shift: float, img_height: int, hop = 3):
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
        debug:dict = field(default_factory=dict)

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

        margin, margin_dict = get_margin(binary_image, int(center_x), int(center_y))
        point.margin = margin
        point.debug = {
            'margin': margin_dict,
        }

        # get density. it is the mean of raw image pixels where b inary image is 1 in the center_x slice
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
        binary_image = cv2.resize(binary_image, (binary_image.shape[1]*4, binary_image.shape[0]*4), interpolation=cv2.INTER_NEAREST)
        for point in points:
            cv2.circle(binary_image, (int(point.x)*4, int(point.y)*4), int(point.margin), (150,120,0), -1)
            margin_dict = point.debug['margin']
            # cv2.line(binary_image, (int(point.x)*4, int(point.y)*4), (int(point.x)*4 + margin_dict['r']*4, int(point.y)*4), (0,0,100), 2)
            # cv2.line(binary_image, (int(point.x)*4, int(point.y)*4), (int(point.x)*4 - margin_dict['l']*4, int(point.y)*4), (0,0,100), 2)
            # cv2.line(binary_image, (int(point.x)*4, int(point.y)*4), (int(point.x)*4, int(point.y)*4 + margin_dict['u']*4), (0,0,100), 2)
            # cv2.line(binary_image, (int(point.x)*4, int(point.y)*4), (int(point.x)*4, int(point.y)*4 - margin_dict['d']*4), (0,0,100), 2)
        cv2.imshow('binary_image', binary_image)
        cv2.waitKey(0)

    parameters: defaultdict[str, list] = defaultdict(list)
    for point in points:
        parameters['intensity'].append(point.margin / 30)
        parameters['density'].append(point.density)
        parameters['hue'].append(point.hue/255)
        parameters['saturation'].append(point.saturation/255)
        parameters['value'].append(point.value/255)
        parameters['pos_x'].append(2*(point.x + x_shift))
        parameters['pos_y'].append(2*(img_height - (point.y + y_shift)))

    return dict(parameters)


@dataclass
class StrokeInfo:
    start_x: int
    start_y: int
    end_x: int
    end_y: int
    length: int
    parameters: dict[str, list] = field(default_factory=dict)

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
            - pos_x: List of x-coordinates for each measurement point
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
    image = cv2.resize(image, (image.shape[1]//2, image.shape[0]//2))
    # border_size = round(image.shape[0] / 2)
    
    # # Add white borders to give space for stroke analysis
    # image = cv2.copyMakeBorder(
    #     image,
    #     top=border_size,
    #     bottom=border_size,
    #     left=0,
    #     right=0,
    #     borderType=cv2.BORDER_CONSTANT,
    #     value=(255, 255, 255)
    # )
    
    # Convert to different color spaces for analysis
    grayscale_image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    hsv_image = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

    # Find strokes in the image
    strokes, binary_image = find_stroke_contours(grayscale_image)

    
    # For visualization if SHOW_PLOTS=True
    visualization_image = image.copy()
    cv2.drawContours(visualization_image, strokes, -1, (0, 255, 0), 2)
    
    stroke_info_list: list[StrokeInfo] = []

    # Process each stroke
    for stroke in strokes:
        stroke_boundary = cv2.boundingRect(stroke)
        x, y, w, h = stroke_boundary
        assert w > 0 and h > 0, "Stroke boundary is invalid"
        roi_slice = slice(y, y+h), slice(x, x+w)

        # shift the stroke with -x,-y
        stroke = stroke - np.array([x, y])

        parameters = stroke_to_parameters(stroke,
            hsv_image[roi_slice],
            binary_image[roi_slice], 
            grayscale_image[roi_slice],
            x,
            y,
            image.shape[0]
        )
        if len(parameters['pos_x']) > 0:
            stroke_info_list.append(StrokeInfo(
                start_x=parameters['pos_x'][0],
                start_y=parameters['pos_y'][0],
                end_x=parameters['pos_x'][-1],
                end_y=parameters['pos_y'][-1],
                length=len(parameters['pos_x']),
                parameters=parameters
            ))
    

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
            plt.plot(parameters['pos_x'], parameters['pitch'], label=f'Stroke {i+1} pitch')
            plt.title("Pitch (MIDI note)")
            plt.legend()
            
            plt.subplot(3, 2, 3)
            plt.plot(parameters['pos_x'], parameters['intensity'], label=f'Stroke {i+1} width')
            plt.title("Width (intensity)")
            
            plt.subplot(3, 2, 5)
            plt.plot(parameters['pos_x'], parameters['density'], label=f'Stroke {i+1} density')
            plt.title("Density")
            
            plt.subplot(3, 2, 2)
            plt.plot(parameters['pos_x'], parameters['hue'], label=f'Stroke {i+1} hue')
            plt.title("Hue")
            
            plt.subplot(3, 2, 4)
            plt.plot(parameters['pos_x'], parameters['saturation'], label=f'Stroke {i+1} saturation')
            plt.title("Saturation")
            
            plt.subplot(3, 2, 6)
            plt.plot(parameters['pos_x'], parameters['value'], label=f'Stroke {i+1} value')
            plt.xlabel("Position")
            plt.title("Value")

        plt.tight_layout()
        plt.show()


    # # Normalize x positions
    # for i in range(len(pos_xs)):
    #     pos_xs[i] = (np.array(pos_xs[i]) / image_width)
    # pos_xs = np.array(pos_xs)

    # print(stroke_intensities)
    
    # result = {
    #     'intensity': stroke_intensities,
    #     'pitch': stroke_pitches,
    #     'density': stroke_densities,
    #     'hue': stroke_hues,
    #     'saturation': stroke_saturations,
    #     'value': stroke_values,
    #     'pos_x': pos_xs
    # }

    return stroke_info_list
