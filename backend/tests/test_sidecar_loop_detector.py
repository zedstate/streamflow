import unittest
import io
import time
import collections
from PIL import Image
from apps.stream.sidecar_loop_detector import SidecarLoopDetector

class MockPipe(io.BytesIO):
    def read(self, size):
        return super().read(size)

class TestSidecarLoopDetector(unittest.TestCase):
    def create_ppm_frame(self, color=(255, 0, 0), dot_pos=(0, 0)):
        width, height = 32, 32
        # Fill with base color
        pixels = list(color) * (width * height)
        # Add a unique "dot" to ensure hash uniqueness
        dot_idx = (dot_pos[1] * width + dot_pos[0]) * 3
        pixels[dot_idx:dot_idx+3] = [255 - color[0], 255 - color[1], 255 - color[2]]
        
        header = f"P6\n{width} {height}\n255\n".encode()
        return header + bytes(pixels)

    def test_ppm_header_parsing(self):
        frame = self.create_ppm_frame((100, 100, 100))
        pipe = MockPipe(frame)
        detector = SidecarLoopDetector(pipe)
        
        parsed_frame = detector._read_ppm_frame()
        self.assertEqual(parsed_frame, frame)

    def test_loop_detection(self):
        # Create a sequence of 3 unique frames with unique dots
        f1 = self.create_ppm_frame((255, 0, 0), (5, 5)) 
        f2 = self.create_ppm_frame((0, 255, 0), (10, 10))
        f3 = self.create_ppm_frame((0, 0, 255), (15, 15))
        
        # Create a looping stream: F1, F2, F3, ..., (Wait 11s) ..., F1, F2, F3
        pipe = MockPipe()
        detector = SidecarLoopDetector(pipe)
        
        # Helper to add frame with timestamp
        def add_frame(f, t_offset):
            # We bypass detector.run() for deterministic testing
            from PIL import Image
            import io
            import imagehash
            img = Image.open(io.BytesIO(f))
            h = imagehash.phash(img)
            detector.buffer.append((time.monotonic() + t_offset, h))
            detector.last_frame_time = time.monotonic() + t_offset

        # Start of sequence
        add_frame(f1, 0)
        add_frame(f2, 1)
        add_frame(f3, 2)
        
        # Some filler in between (not matching the sequence)
        for i in range(10):
            add_frame(self.create_ppm_frame((i, i, i)), 3 + i)
            
        # Re-occurrence of the sequence after 12 seconds
        add_frame(f1, 15)
        add_frame(f2, 16)
        add_frame(f3, 17)
        
        # Detection should find the loop
        duration = detector.detect_loop()
        self.assertIsNotNone(duration)
        self.assertGreaterEqual(duration, 10.0)

    def test_static_image_rejection(self):
        f1 = self.create_ppm_frame((255, 0, 0))
        pipe = MockPipe()
        detector = SidecarLoopDetector(pipe)
        
        def add_frame(f, t_offset):
            from PIL import Image
            import io
            import imagehash
            img = Image.open(io.BytesIO(f))
            h = imagehash.phash(img)
            detector.buffer.append((time.monotonic() + t_offset, h))
            detector.last_frame_time = time.monotonic() + t_offset

        # Add 10 identical frames
        for i in range(10):
            add_frame(f1, i)
            
        # Should NOT detect a loop (it's a static image)
        duration = detector.detect_loop()
        self.assertIsNone(duration)

if __name__ == '__main__':
    unittest.main()
