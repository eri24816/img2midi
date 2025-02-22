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
BINARY_THRESHOLD = 240

def find_stroke_contours(grayscale_image):
    """Find contours of strokes in the image"""
    # Convert to binary image
    _, binary_image = cv2.threshold(grayscale_image, BINARY_THRESHOLD, 255, cv2.THRESH_BINARY_INV)

    # Smooth image to improve contour detection
    blurred_image = cv2.GaussianBlur(binary_image, (7, 7), 0)

    # Dilate to connect nearby regions
    kernel = np.ones((5, 5), np.uint8)
    dilated_image = cv2.dilate(blurred_image, kernel, iterations=1)

    # Close gaps in strokes
    closed_image = cv2.morphologyEx(dilated_image, cv2.MORPH_CLOSE, kernel)

    # Find contours
    contours, _ = cv2.findContours(closed_image, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    return contours

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

def notation_to_parameters(image_input) -> dict[str, np.ndarray]:
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
    image = cv2.resize(image, (1600, 100))
    max_analysis_height = 100
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
    image_height = image.shape[0]
    image_width = image.shape[1]
    
    # Find strokes in the image
    strokes = find_stroke_contours(grayscale_image)
    
    # For visualization if SHOW_PLOTS=True
    visualization_image = image.copy()
    cv2.drawContours(visualization_image, strokes, -1, (0, 255, 0), 2)
    
    # Analysis parameters
    analysis_step = 10  # Distance between analysis points
    analysis_width = analysis_step * 2  # Width of analysis window

    # Initialize lists to store parameters
    stroke_pitches = []
    stroke_intensities = []
    stroke_densities = []
    stroke_hues = []
    stroke_saturations = []
    stroke_values = []
    x_positions = []

    assert len(strokes) > 0, "No strokes found in the image"
    assert len(strokes) <= 1, "Currently only one stroke is supported. Found {} strokes".format(len(strokes))
    
    # Process each stroke
    for stroke in strokes:
        x, y, width, height = cv2.boundingRect(stroke)
        
        # Initialize lists for current stroke measurements
        intensity_measurements = []
        pitch_measurements = []
        density_measurements = []
        hue_measurements = []
        value_measurements = []
        saturation_measurements = []
        stroke_angles = []
        x_positions = [range(x, x + width - analysis_width, analysis_step)] + x_positions
        
        # Analyze stroke from left to right
        for current_x in x_positions[0]:
            slice_width = min(analysis_width, x + width - current_x)
            image_slice = grayscale_image[y:y + height, current_x:current_x + slice_width]
            
            # Find stroke boundaries
            top_edges, bottom_edges = find_stroke_boundaries(image_slice, slice_width, y, image_height)
            midline = (top_edges + bottom_edges) / 2
            slice_height = min(max_analysis_height, round(np.max(top_edges) - np.min(bottom_edges)))
            
            # Calculate stroke angle and rotate analysis window
            center_x = (current_x + slice_width / 2)
            center_y = np.mean(midline)
            stroke_angle = np.arctan2(1, np.mean(np.diff(midline)))
            stroke_angles.append(stroke_angle)
            rotation_matrix = cv2.getRotationMatrix2D((float(center_x), float(center_y)), -np.degrees(stroke_angle)+90, 1.0)
            rotated_image = cv2.warpAffine(hsv_image, rotation_matrix, (image_width, image_height))
            slice_hsv = cv2.getRectSubPix(rotated_image, (slice_width, slice_height), (float(center_x), float(center_y)))
            slice_bgr = cv2.cvtColor(slice_hsv, cv2.COLOR_HSV2BGR)
            slice_gray = cv2.cvtColor(slice_bgr, cv2.COLOR_BGR2GRAY)
            
            # Get rotated boundaries
            top_edges, bottom_edges = find_stroke_boundaries(slice_gray, slice_width, 0, slice_height)
            
            # Calculate stroke width (intensity)
            stroke_width = np.mean(top_edges - bottom_edges)
            intensity_measurements.append(stroke_width / max_analysis_height)  # Normalize by max height
            
            # Calculate pitch from vertical position
            vertical_position = center_y
            pitch = (1 - vertical_position / image_height) * (PITCH_RANGE[1] - PITCH_RANGE[0]) + PITCH_RANGE[0]
            pitch_measurements.append(np.mean(pitch))
            
            # Extract pixels for color analysis
            gray_pixels = []
            hsv_pixels = []
            stroke_pixels = []
            total_pixels = []
            for x_offset in range(slice_width):
                for y_offset in range(int(bottom_edges[x_offset]), int(top_edges[x_offset])):
                    if slice_gray[y_offset, x_offset] <= 223:
                        gray_pixels.append(slice_gray[y_offset, x_offset])
                        hsv_pixels.append(slice_hsv[y_offset, x_offset, :])
                        stroke_pixels.append((y_offset, x_offset))
                    total_pixels.append((y_offset, x_offset))
            gray_pixels = np.array(gray_pixels)
            hsv_pixels = np.array(hsv_pixels)
            stroke_pixels = np.array(stroke_pixels)
            total_pixels = np.array(total_pixels)
            
            # Calculate density and color attributes
            if stroke_pixels.shape[0] > 0:
                density = stroke_pixels.shape[0] / total_pixels.shape[0]
                mean_hue = np.mean(hsv_pixels[:, 0])
                mean_saturation = np.mean(hsv_pixels[:, 1])
                mean_value = np.mean(hsv_pixels[:, 2])
            else:
                density = 0
                mean_hue = 0
                mean_saturation = 0
                mean_value = 0
            
            density_measurements.append(density)
            hue_measurements.append(mean_hue)
            saturation_measurements.append(mean_saturation / 256)
            value_measurements.append(mean_value / 256)
        
        # Add stroke measurements to overall lists using append
        stroke_intensities.append(intensity_measurements)
        stroke_pitches.append(pitch_measurements)
        stroke_densities.append(density_measurements)
        stroke_hues.append(hue_measurements)
        stroke_saturations.append(saturation_measurements)
        stroke_values.append(value_measurements)

    # reverse the lists and convert to numpy arrays
    stroke_intensities = np.array(stroke_intensities[::-1])
    stroke_pitches = np.array(stroke_pitches[::-1])
    stroke_densities = np.array(stroke_densities[::-1])
    stroke_hues = np.array(stroke_hues[::-1])
    stroke_saturations = np.array(stroke_saturations[::-1])
    stroke_values = np.array(stroke_values[::-1])

    # Visualization code
    if SHOW_PLOTS:
        plt.imshow(visualization_image)
        plt.title("Detected Strokes")
        plt.axis('off')
        plt.show()
        
        plt.figure(figsize=(14, 8))
        for i, (intensity, pitch, density, hue, saturation, value, x) in enumerate(zip(
                stroke_intensities, stroke_pitches, 
                stroke_densities, stroke_hues, 
                stroke_saturations, stroke_values, x_positions)):
            plt.subplot(3, 2, 1)
            plt.plot(x, pitch, label=f'Stroke {i+1} pitch')
            plt.title("Pitch (MIDI note)")
            plt.legend()
            
            plt.subplot(3, 2, 3)
            plt.plot(x, intensity, label=f'Stroke {i+1} width')
            plt.title("Width (intensity)")
            
            plt.subplot(3, 2, 5)
            plt.plot(x, density, label=f'Stroke {i+1} density')
            plt.title("Density")
            
            plt.subplot(3, 2, 2)
            plt.plot(x, hue, label=f'Stroke {i+1} hue')
            plt.title("Hue")
            
            plt.subplot(3, 2, 4)
            plt.plot(x, saturation, label=f'Stroke {i+1} saturation')
            plt.title("Saturation")
            
            plt.subplot(3, 2, 6)
            plt.plot(x, value, label=f'Stroke {i+1} value')
            plt.xlabel("Position")
            plt.title("Value")

        plt.tight_layout()
        plt.show()
        
    # Normalize x positions
    for i in range(len(x_positions)):
        x_positions[i] = (np.array(x_positions[i]) / image_width)
    x_positions = np.array(x_positions)

    print(stroke_intensities)
    
    result = {
        'intensity': stroke_intensities,
        'pitch': stroke_pitches,
        'density': stroke_densities,
        'hue': stroke_hues,
        'saturation': stroke_saturations,
        'value': stroke_values,
        'x_position': x_positions
    }

    return result
