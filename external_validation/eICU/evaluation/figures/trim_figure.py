from PIL import Image

def trim_image(path, save_path=None):
    # Open the image
    img = Image.open(path).convert("RGBA")  # ensure alpha channel
    # Crop to bounding box of non-transparent / non-white content
    bbox = img.getbbox()
    if bbox:
        img = img.crop(bbox)
    # Save to new file if requested
    if save_path:
        img.save(save_path)
    return img

# Paths
input_path = "evaluation/figures/composite_performance_figure.png"
output_path = "evaluation/figures/composite_performance_figure_trimmed.png"

# Trim and save
trim_image(input_path, save_path=output_path)