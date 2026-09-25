import os
import cv2
import numpy as np


def generate_realistic_patrol_video(
    output_path: str = "mock_streams/sample_patrol.mp4",
    num_frames: int = 60,
    fps: int = 15
):
    """
    Generates a 4-second surveillance video featuring real objects (persons, bus)
    using the bundled standard benchmark frames with camera pan/zoom motion.
    """
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    # Locate bundled standard test images
    try:
        from ultralytics.utils import ASSETS
        bus_img_path = os.path.join(str(ASSETS), "bus.jpg")
        zidane_img_path = os.path.join(str(ASSETS), "zidane.jpg")
    except ImportError:
        bus_img_path = ""
        zidane_img_path = ""

    img_bus = cv2.imread(bus_img_path) if os.path.exists(bus_img_path) else None
    img_zidane = cv2.imread(zidane_img_path) if os.path.exists(zidane_img_path) else None

    target_w, target_h = 640, 480
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(output_path, fourcc, float(fps), (target_w, target_h))

    for i in range(num_frames):
        # Choose image or blend to simulate camera pan
        if img_bus is not None and (i < num_frames // 2 or img_zidane is None):
            src_frame = cv2.resize(img_bus, (target_w, target_h))
        elif img_zidane is not None:
            src_frame = cv2.resize(img_zidane, (target_w, target_h))
        else:
            src_frame = np.ones((target_h, target_w, 3), dtype=np.uint8) * 45

        # Apply slight camera pan effect
        shift_x = int(np.sin(i / 5.0) * 8)
        M = np.float32([[1, 0, shift_x], [0, 1, 0]])
        frame = cv2.warpAffine(src_frame, M, (target_w, target_h))

        writer.write(frame)

    writer.release()
    print(f"Generated realistic patrol test video: {output_path} ({num_frames} frames @ {fps} FPS)")


if __name__ == "__main__":
    generate_realistic_patrol_video()
