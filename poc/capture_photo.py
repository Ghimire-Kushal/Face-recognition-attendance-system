"""
Capture test photos from your webcam.

Usage:
    python poc/capture_photo.py out.jpg

Controls:
    SPACE - save current frame to <out.jpg> (adds _2, _3... if it already exists)
    Q     - quit
"""
import sys
import os
import cv2


def next_available_path(path: str) -> str:
    if not os.path.exists(path):
        return path
    base, ext = os.path.splitext(path)
    i = 2
    while os.path.exists(f"{base}_{i}{ext}"):
        i += 1
    return f"{base}_{i}{ext}"


def main():
    if len(sys.argv) != 2:
        print("Usage: python poc/capture_photo.py <output.jpg>")
        sys.exit(1)

    out_path = sys.argv[1]

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Could not open webcam. On macOS: grant camera permission to your terminal/IDE in System Settings > Privacy & Security > Camera.")
        sys.exit(1)

    print("SPACE = save photo, Q = quit")

    while True:
        ok, frame = cap.read()
        if not ok:
            print("Failed to read frame from camera")
            break

        display = frame.copy()
        cv2.putText(display, "SPACE = save   Q = quit", (20, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        cv2.imshow("capture_photo - press SPACE to save", display)

        key = cv2.waitKey(1) & 0xFF
        if key == ord(" "):
            save_path = next_available_path(out_path)
            cv2.imwrite(save_path, frame)
            print(f"Saved {save_path}")
        elif key == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
