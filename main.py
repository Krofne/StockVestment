import os
import requests
from flask import Flask, request, render_template_string
from PIL import Image, ImageDraw, ImageFont
import subprocess
import ipaddress

# Replace with your IPInfo API token
IPINFO_TOKEN = os.getenv("IPINFO_TOKEN")

# Initialize Flask app
app = Flask(__name__)

# Store the previous IP address
previous_ip = None

# Check if the IP is private
def is_private_ip(ip_str):
    try:
        ip = ipaddress.ip_address(ip_str)
        return ip.is_private
    except ValueError:
        return False

@app.route("/", methods=["GET"])
def handler():
    global previous_ip

    # Get the client IP
    ip_addr = request.remote_addr  # Use remote_addr to detect the actual client IP directly

    # Check for proxies (headers like X-Forwarded-For or X-Real-IP might contain the actual client IP)
    forwarded_for = request.headers.get('X-Forwarded-For')
    real_ip = request.headers.get('X-Real-IP')

    # If we have a forwarded IP, use that instead of the remote_addr
    if forwarded_for:
        ip_addr = forwarded_for.split(",")[0]
    elif real_ip:
        ip_addr = real_ip

    # Print both the remote_addr and forwarded IP (for debugging)
    print(f"remote_addr: {request.remote_addr}")
    print(f"X-Forwarded-For: {forwarded_for}")
    print(f"X-Real-IP: {real_ip}")
    print(f"Client IP: {ip_addr}")  # For debugging

    # Handle the case where the IP might be a private one
    if is_private_ip(ip_addr):
        ip_addr = "8.8.8.8"  # Fallback to a public IP if private IP is detected

    # Check if the IP has changed
    ip_changed = ip_addr != previous_ip
    if ip_changed:
        previous_ip = ip_addr

    # Fetch IP info from IPInfo API
    try:
        ip_info = get_ipinfo_data(ip_addr)
        print(f"IPInfo data: {ip_info}")

        # Generate the video with overlay
        video_file_path = generate_video(ip_addr, ip_info)

        # Return an HTML page with the embedded video and auto-refresh if IP changes
        return render_template_string("""
            <!doctype html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Generated Video</title>
                {% if ip_changed %}
                <meta http-equiv="refresh" content="5">
                {% endif %}
            </head>
            <body>
                <h1>Generated Video for IP: {{ ip_addr }}</h1>
                <video width="640" height="360" controls>
                    <source src="{{ video_file_path }}" type="video/mp4">
                    Your browser does not support the video tag.
                </video>
            </body>
            </html>
        """, ip_addr=ip_addr, video_file_path=video_file_path, ip_changed=ip_changed)

    except Exception as e:
        print(f"Error fetching IPInfo data: {e}")
        return "418 - I'm a teapot", 418

def get_ipinfo_data(ip_str):
    """Function to fetch IP information from IPInfo API."""
    url = f"https://ipinfo.io/{ip_str}/json?token={IPINFO_TOKEN}"
    response = requests.get(url)

    if response.status_code != 200:
        raise Exception(f"Error fetching IPInfo data: {response.status_code}")

    return response.json()

def generate_image(ip_str, ip_info):
    """Generate an image with IP information."""
    # Use a default image as background (use your own path here)
    base_image_path = "image.png"  # Update this to your actual template image path
    img = Image.open(base_image_path)
    draw = ImageDraw.Draw(img)

    # Create the text to overlay
    text = f"IP: {ip_str}\nCity: {ip_info['city']}\nRegion: {ip_info['region']}\nCountry: {ip_info['country']}"
    font = ImageFont.load_default()

    # Position of text
    draw.text((50, 50), text, font=font, fill="white")

    # Save the generated image
    img_path = f"/tmp/{ip_str.replace('.', '')}_image.png"
    img.save(img_path)

    return img_path

def generate_video(ip_str, ip_info):
    """Generate a video with overlayed IP information image."""
    video_template_path = "video.mp4"  # Update this to your actual template video path

    # Generate an image with the IP info
    image_path = generate_image(ip_str, ip_info)

    # Ensure the static folder exists
    if not os.path.exists("static"):
        os.makedirs("static")

    # Save the output video to the static folder
    output_video_path = f"static/{ip_str.replace('.', '')}_output_video.mp4"

    # FFmpeg command to overlay the image onto the video
    cmd = [
        "ffmpeg",
        "-y",  # Automatically overwrite any existing file
        "-i", video_template_path,
        "-i", image_path,
        "-filter_complex", "[0:v][1:v] overlay=0:0",
        "-c:v", "libx264",
        "-c:a", "copy",
        "-preset", "ultrafast",
        output_video_path
    ]

    subprocess.run(cmd, check=True)

    # Clean up the image file after video generation
    os.remove(image_path)

    return output_video_path

if __name__ == "__main__":
    # Ensure IPINFO_TOKEN is set
    if not IPINFO_TOKEN:
        print("Error: IPINFO_TOKEN environment variable not set.")
        exit(1)

    # Start the Flask app
    app.run(debug=True, host="0.0.0.0", port=3000)
