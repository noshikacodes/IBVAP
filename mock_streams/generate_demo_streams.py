"""
IBVAP Multi-Camera Surveillance Video Generator
Generates 4 distinct, military-grade simulated CCTV video streams for border defense C2:
- CAM_01: Sector Alpha - North Perimeter Gate (Daylight checkpoint with vehicle & barrier)
- CAM_02: Sector Alpha - South Vehicle Corridor (Transit route with ANPR tracking box)
- CAM_03: Sector Bravo - East Virtual Fence (FLIR / Thermal Night Vision with virtual tripwire)
- CAM_04: Sector Bravo - West Outpost (Hilltop PTZ sweep with tactical crosshairs & HUD)
"""

import os
import cv2
import numpy as np


def draw_tactical_hud(frame, cam_id, title, mode_text, frame_idx, total_frames):
    h, w = frame.shape[:2]
    # Header bar
    cv2.rectangle(frame, (0, 0), (w, 24), (15, 23, 42), -1)
    cv2.putText(frame, f"IBVAP C2 // {cam_id} - {title}", (8, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (56, 189, 248), 1, cv2.LINE_AA)
    cv2.putText(frame, mode_text, (w - 110, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (34, 197, 94), 1, cv2.LINE_AA)
    
    # Bottom status bar
    cv2.rectangle(frame, (0, h - 22), (w, h), (15, 23, 42), -1)
    ts = f"FRAME: {frame_idx:04d}/{total_frames:04d} | 15.0 FPS | 640x480 H.264"
    cv2.putText(frame, ts, (8, h - 7), cv2.FONT_HERSHEY_SIMPLEX, 0.36, (148, 163, 184), 1, cv2.LINE_AA)
    cv2.putText(frame, "STATUS: SECURE", (w - 115, h - 7), cv2.FONT_HERSHEY_SIMPLEX, 0.36, (34, 197, 94), 1, cv2.LINE_AA)


def generate_cam01_gate(output_path="mock_streams/cam01_gate.mp4", num_frames=120, fps=15):
    """CAM_01: Perimeter Gate with moving vehicle and security barrier."""
    w, h = 640, 480
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(output_path, fourcc, float(fps), (w, h))

    for i in range(num_frames):
        frame = np.zeros((h, w, 3), dtype=np.uint8)
        # Background: Sky & Ground
        frame[:220, :] = [60, 50, 40]  # Dusk sky
        frame[220:, :] = [35, 40, 45]  # Asphalt & terrain

        # Road
        pts = np.array([[200, 220], [440, 220], [580, 460], [60, 460]], np.int32)
        cv2.fillPoly(frame, [pts], (50, 55, 60))
        cv2.line(frame, (320, 220), (320, 460), (200, 200, 200), 2, cv2.LINE_AA)

        # Gate Checkpost Booth
        cv2.rectangle(frame, (70, 160), (190, 320), (70, 80, 90), -1)
        cv2.rectangle(frame, (65, 150), (195, 165), (100, 115, 130), -1)
        cv2.rectangle(frame, (90, 190), (170, 250), (180, 220, 240), -1)  # Window

        # Security Boom Barrier (Angle oscillates)
        barrier_angle = np.sin(i / 15.0) * 0.3 + 0.3
        bar_len = 160
        bx2 = int(190 + bar_len * np.cos(barrier_angle))
        by2 = int(270 - bar_len * np.sin(barrier_angle))
        cv2.line(frame, (190, 270), (bx2, by2), (0, 0, 220), 5)
        cv2.line(frame, (190, 270), (bx2, by2), (255, 255, 255), 2)

        # Moving Vehicle (Patrol SUV approaching)
        t = (i % 60) / 60.0
        car_scale = 0.5 + 0.8 * t
        car_x = int(280 + 20 * np.sin(i / 10.0))
        car_y = int(240 + 140 * t)
        cw, ch = int(120 * car_scale), int(70 * car_scale)
        
        # Vehicle body
        cv2.rectangle(frame, (car_x - cw // 2, car_y - ch // 2), (car_x + cw // 2, car_y + ch // 2), (30, 70, 30), -1)
        cv2.rectangle(frame, (car_x - cw // 3, car_y - ch // 2 - int(20 * car_scale)), (car_x + cw // 3, car_y - ch // 2), (20, 50, 20), -1)
        # Headlights
        cv2.circle(frame, (car_x - cw // 3, car_y + ch // 3), int(6 * car_scale), (200, 255, 255), -1)
        cv2.circle(frame, (car_x + cw // 3, car_y + ch // 3), int(6 * car_scale), (200, 255, 255), -1)
        # License plate
        cv2.rectangle(frame, (car_x - int(22 * car_scale), car_y + int(12 * car_scale)), (car_x + int(22 * car_scale), car_y + int(24 * car_scale)), (240, 240, 240), -1)
        cv2.putText(frame, "DL01AB", (car_x - int(18 * car_scale), car_y + int(21 * car_scale)), cv2.FONT_HERSHEY_SIMPLEX, 0.25 * car_scale, (0, 0, 0), 1)

        draw_tactical_hud(frame, "CAM_01", "NORTH GATE", "DAYLIGHT / COLOR", i, num_frames)
        writer.write(frame)

    writer.release()
    print(f"[OK] Generated CAM_01 Gate Video: {output_path}")


def generate_cam02_corridor(output_path="mock_streams/cam02_corridor.mp4", num_frames=120, fps=15):
    """CAM_02: Transit Corridor with ANPR recognition and vehicle bounding boxes."""
    w, h = 640, 480
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(output_path, fourcc, float(fps), (w, h))

    for i in range(num_frames):
        frame = np.zeros((h, w, 3), dtype=np.uint8)
        # Highway Corridor
        frame[:180, :] = [45, 40, 35]
        frame[180:, :] = [25, 30, 35]

        # Multi-lane roadway
        cv2.fillPoly(frame, [np.array([[120, 180], [520, 180], [640, 460], [0, 460]])], (40, 45, 50))
        # Lane divider dashes
        for lane_x in [240, 400]:
            dash_y = int((i * 8) % 40)
            for dy in range(180 + dash_y, 460, 40):
                cv2.line(frame, (lane_x, dy), (lane_x, min(dy + 20, 455)), (220, 220, 220), 2)

        # Moving Truck in Lane 1
        t1 = (i % 80) / 80.0
        truck_x = int(180 + 30 * t1)
        truck_y = int(190 + 200 * t1)
        tw, th = int(70 + 80 * t1), int(50 + 60 * t1)
        cv2.rectangle(frame, (truck_x - tw // 2, truck_y - th // 2), (truck_x + tw // 2, truck_y + th // 2), (90, 50, 30), -1)
        # ANPR Scan Box
        cv2.rectangle(frame, (truck_x - tw // 2 - 4, truck_y - th // 2 - 4), (truck_x + tw // 2 + 4, truck_y + th // 2 + 4), (0, 255, 0), 2)
        cv2.putText(frame, "ANPR: 22BH1234AA [0.94]", (truck_x - tw // 2, truck_y - th // 2 - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (0, 255, 0), 1)

        # Moving Fast Patrol in Lane 2
        t2 = ((i + 40) % 60) / 60.0
        p_x = int(420 - 40 * t2)
        p_y = int(190 + 220 * t2)
        pw, ph = int(50 + 70 * t2), int(35 + 50 * t2)
        cv2.rectangle(frame, (p_x - pw // 2, p_y - ph // 2), (p_x + pw // 2, p_y + ph // 2), (40, 40, 110), -1)
        cv2.rectangle(frame, (p_x - pw // 2 - 4, p_y - ph // 2 - 4), (p_x + pw // 2 + 4, p_y + ph // 2 + 4), (56, 189, 248), 2)
        cv2.putText(frame, "PATROL_UNIT // ID:44", (p_x - pw // 2, p_y - ph // 2 - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (56, 189, 248), 1)

        draw_tactical_hud(frame, "CAM_02", "VEHICLE CORRIDOR", "ANPR ACTIVE", i, num_frames)
        writer.write(frame)

    writer.release()
    print(f"[OK] Generated CAM_02 Corridor Video: {output_path}")


def generate_cam03_fence(output_path="mock_streams/cam03_fence.mp4", num_frames=120, fps=15):
    """CAM_03: FLIR Thermal / Night Vision Perimeter Fence with Intrusion Detection."""
    w, h = 640, 480
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(output_path, fourcc, float(fps), (w, h))

    for i in range(num_frames):
        # Thermal Green Phosphor background
        frame = np.zeros((h, w, 3), dtype=np.uint8)
        frame[:, :] = [10, 40, 15]

        # Terrain contours
        for step in range(0, w, 30):
            th_h = int(260 + 20 * np.sin(step / 40.0))
            cv2.line(frame, (step, th_h), (step + 30, th_h), (20, 80, 30), 2)
        frame[280:, :] = [15, 60, 20]

        # Barbed Wire Fence Posts
        for px in range(40, w, 90):
            cv2.line(frame, (px, 200), (px, 380), (80, 180, 90), 3)
            # Cross wire
            cv2.line(frame, (px - 45, 240), (px + 45, 240), (60, 140, 70), 1)
            cv2.line(frame, (px - 45, 300), (px + 45, 300), (60, 140, 70), 1)

        # Virtual Tripwire (Geofence Line)
        tripwire_color = (0, 0, 255) if (i % 30 < 15 and i > 40) else (0, 255, 255)
        cv2.line(frame, (60, 320), (580, 320), tripwire_color, 2)
        cv2.putText(frame, "[VIRTUAL FENCE TRIPWIRE - EXCLUSION ZONE]", (140, 312), cv2.FONT_HERSHEY_SIMPLEX, 0.38, tripwire_color, 1)

        # Thermal Intruder Target (Hot signature moving across fence)
        t3 = (i % 120) / 120.0
        intruder_x = int(120 + 380 * t3)
        intruder_y = int(300 + 15 * np.sin(i / 4.0))
        # Thermal glow
        cv2.circle(frame, (intruder_x, intruder_y - 20), 18, (120, 255, 140), -1)  # Head
        cv2.ellipse(frame, (intruder_x, intruder_y + 10), (14, 25), 0, 0, 360, (180, 255, 200), -1)  # Torso
        
        # Threat Box
        if intruder_x > 260:
            cv2.rectangle(frame, (intruder_x - 22, intruder_y - 45), (intruder_x + 22, intruder_y + 40), (0, 0, 255), 2)
            cv2.putText(frame, "! INTRUSION DETECTED !", (intruder_x - 55, intruder_y - 52), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (0, 0, 255), 1)

        draw_tactical_hud(frame, "CAM_03", "VIRTUAL FENCE", "FLIR THERMAL NVG", i, num_frames)
        writer.write(frame)

    writer.release()
    print(f"[OK] Generated CAM_03 Fence Video: {output_path}")


def generate_cam04_outpost(output_path="mock_streams/cam04_outpost.mp4", num_frames=120, fps=15):
    """CAM_04: Standby Hilltop Tower PTZ Camera with pan-tilt sweep and crosshairs."""
    w, h = 640, 480
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(output_path, fourcc, float(fps), (w, h))

    for i in range(num_frames):
        frame = np.zeros((h, w, 3), dtype=np.uint8)
        # Pan offset
        pan_offset = int(np.sin(i / 20.0) * 60)
        tilt_offset = int(np.cos(i / 25.0) * 20)

        # Mountain Landscape background
        frame[:240 + tilt_offset, :] = [80, 70, 50]
        # Distant ridge
        pts_ridge = np.array([
            [-50 + pan_offset, 220 + tilt_offset],
            [150 + pan_offset, 160 + tilt_offset],
            [350 + pan_offset, 210 + tilt_offset],
            [550 + pan_offset, 140 + tilt_offset],
            [750 + pan_offset, 230 + tilt_offset],
            [750, 480],
            [-50, 480]
        ], np.int32)
        cv2.fillPoly(frame, [pts_ridge], (45, 55, 40))

        # Forward Watchtower
        tower_x = 320 + pan_offset
        tower_y = 200 + tilt_offset
        cv2.rectangle(frame, (tower_x - 35, tower_y), (tower_x + 35, tower_y + 160), (35, 40, 45), -1)
        cv2.rectangle(frame, (tower_x - 55, tower_y - 30), (tower_x + 55, tower_y), (60, 70, 75), -1)
        cv2.line(frame, (tower_x, tower_y - 60), (tower_x, tower_y - 30), (180, 180, 180), 2)  # Antenna

        # Tactical PTZ Reticle & Crosshairs
        cx, cy = w // 2, h // 2
        cv2.circle(frame, (cx, cy), 60, (56, 189, 248), 1)
        cv2.circle(frame, (cx, cy), 4, (56, 189, 248), -1)
        cv2.line(frame, (cx - 90, cy), (cx - 20, cy), (56, 189, 248), 1)
        cv2.line(frame, (cx + 20, cy), (cx + 90, cy), (56, 189, 248), 1)
        cv2.line(frame, (cx, cy - 90), (cx, cy - 20), (56, 189, 248), 1)
        cv2.line(frame, (cx, cy + 20), (cx, cy + 90), (56, 189, 248), 1)

        # PTZ Telemetry Data on Screen
        pan_deg = (pan_offset / 60.0) * 45.0
        tilt_deg = (tilt_offset / 20.0) * 15.0
        zoom_val = 1.0 + 0.5 * (1.0 + np.sin(i / 15.0))
        ptz_info = f"PTZ: PAN {pan_deg:+05.1f}deg | TILT {tilt_deg:+05.1f}deg | ZOOM {zoom_val:.1f}X"
        cv2.putText(frame, ptz_info, (cx - 130, cy + 85), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (56, 189, 248), 1, cv2.LINE_AA)

        draw_tactical_hud(frame, "CAM_04", "WEST OUTPOST TOWER", "PTZ SLEW-TO-CUE", i, num_frames)
        writer.write(frame)

    writer.release()
    print(f"[OK] Generated CAM_04 Outpost Video: {output_path}")


def main():
    os.makedirs("mock_streams", exist_ok=True)
    generate_cam01_gate()
    generate_cam02_corridor()
    generate_cam03_fence()
    generate_cam04_outpost()
    # Also update sample_patrol.mp4 as alias
    generate_cam01_gate("mock_streams/sample_patrol.mp4")
    print("\n[SUCCESS] All 4 multi-sector surveillance demo videos generated successfully!")


if __name__ == "__main__":
    main()
