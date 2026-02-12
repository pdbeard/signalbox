#!/usr/bin/env python3
"""
Generate simple green and red status icons for the system tray.
This is a one-time script to create basic icons.
"""
from PIL import Image, ImageDraw

def create_icon(color_name, rgb_color, size=64):
    """
    Create a simple circular icon with the specified color.
    
    Args:
        color_name: Name for the output file (e.g., 'green', 'red')
        rgb_color: RGB tuple for the icon color
        size: Size of the icon in pixels
    """
    # Create image with transparent background
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Draw a filled circle
    margin = 4
    draw.ellipse([margin, margin, size-margin, size-margin], fill=rgb_color)
    
    # Add a border for better visibility
    border_width = 2
    draw.ellipse([margin, margin, size-margin, size-margin], 
                 outline=(0, 0, 0, 200), width=border_width)
    
    # Save the icon
    output_path = f"core/icons/{color_name}.png"
    img.save(output_path, "PNG")
    print(f"Created {output_path}")

if __name__ == "__main__":
    # Create green icon (success)
    create_icon("green", (76, 175, 80))  # Material Design Green 500
    
    # Create red icon (failure)
    create_icon("red", (244, 67, 54))  # Material Design Red 500
    
    print("\nIcons created successfully!")
    print("You can replace these with custom SVG/PNG icons if desired.")
