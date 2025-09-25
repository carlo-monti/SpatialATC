import math
import tkinter as tk
import numpy as np

def calculate_azimuth(lat1: float, lon1: float, lat2: float, lon2: float, heading=0) -> float:
    """
    Calculate the azimuth (bearing) from point 1 (lat1, lon1) to point 2 (lat2, lon2) in decimal degrees.
    Returns the azimuth in degrees (0° to 360°), with 0° = North, 90° = East, etc.
    If a heading is provided, the bearing is relative (relative bearing) to that
    an object positioned on the right have 90 bearing whereas an object positioned on the left has 270 bearing.
    
    Example usage:
        
    center = (45.62066, 8.71518)       # malpensa twr
    object = (45.64431, 8.77257)     # campanile cardano
    #object = (45.67406, 8.74342)    # serbatoio casorate
    #object = (45.59970, 8.75405)    # campanile lonate pozzolo
    azimuth = calculate_azimuth(center[0], center[1], object[0], object[1], heading=270)
    print(f"Azimuth: {azimuth}°")  # Output: Azimuth: 224.4°
    """
    # Convert degrees to radians
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)
    
    # Calculate longitude difference (Δλ)
    delta_lambda = lon2_rad - lon1_rad
    
    # Compute components for azimuth formula
    x = math.sin(delta_lambda) * math.cos(lat2_rad)
    y = (math.cos(lat1_rad) * math.sin(lat2_rad) 
        - math.sin(lat1_rad) * math.cos(lat2_rad) 
        * math.cos(delta_lambda))
    
    # Calculate azimuth in radians and convert to degrees
    theta_rad = math.atan2(x, y)
    theta_deg = math.degrees(theta_rad)
    
    # Normalize to 0–360°
    azimuth = (theta_deg + 360) % 360
    return (round(azimuth) - heading + 360) % 360

from math import atan, degrees

def calculate_elevation(latA, lonA, hA, latB, lonB, hB):
    """
    This function calculates the elevation angle of point A as seen from point B.
    Calculate the elevation angle from point B to point A.
    Assumes Earth is flat and distances are small near 45° latitude.
    
    Parameters:
        latA, lonA: Latitude and Longitude of point A (in degrees)
        hA: Elevation of point A (in feet)
        latB, lonB: Latitude and Longitude of point B (in degrees)
        hB: Elevation of point B (in feet)
    
    Returns:
        float: Elevation angle from B to A in degrees
    """
    # Constants for conversion at ~45° latitude
    feet_per_deg_lat = 364000
    feet_per_deg_lon = 258720

    # Differences in position
    delta_lat = latA - latB
    delta_lon = lonA - lonB

    # Convert lat/lon differences to feet
    dy = delta_lat * feet_per_deg_lat
    dx = delta_lon * feet_per_deg_lon

    # Total horizontal ground distance
    horizontal_distance = math.sqrt(dx**2 + dy**2)

    # Elevation difference
    delta_h = hA - hB

    # Compute elevation angle
    angle_rad = atan(delta_h / horizontal_distance)
    angle_deg = degrees(angle_rad)

    return angle_deg

def head_tracker_to_spherical(yaw, pitch, roll):
    """
    Convert head tracker signal (yaw, pitch, roll) to azimuth and elevation.

    Parameters:
    x (float): Position along the x-axis
    y (float): Position along the y-axis
    z (float): Position along the z-axis
    yaw (float): Yaw angle in degrees
    pitch (float): Pitch angle in degrees
    roll (float): Roll angle in degrees (not used for direction calculation)

    Returns:
    tuple: (azimuth, elevation) in degrees
    """
    # Convert angles from degrees to radians
    yaw_rad = np.radians(yaw)
    pitch_rad = np.radians(pitch)
    
    # Calculate the direction vector based on yaw and pitch
    dx = np.cos(pitch_rad) * np.sin(yaw_rad)
    dy = np.sin(pitch_rad)
    dz = np.cos(pitch_rad) * np.cos(yaw_rad)
    
    # Calculate azimuth and elevation
    azimuth = np.arctan2(dy, dx)  # in radians
    elevation = np.arcsin(dz / np.sqrt(dx**2 + dy**2 + dz**2))  # in radians
    
    # Convert azimuth and elevation to degrees
    azimuth_deg = np.degrees(azimuth)
    elevation_deg = np.degrees(elevation)
    
    return azimuth_deg, elevation_deg

class CompassWidget2(tk.Frame):
    def __init__(self, parent, width=300, height=300, radius=100, **kwargs):
        super().__init__(parent, **kwargs)
        self.canvas = tk.Canvas(self, width=width, height=height, bg='white', highlightthickness=0)
        self.canvas.pack()

        self.center_x = width // 2
        self.center_y = height // 2
        self.radius = radius

        # White background circle
        self.canvas.create_oval(
            self.center_x - radius - 10, self.center_y - radius - 10,
            self.center_x + radius + 10, self.center_y + radius + 10,
            fill='white', outline='black', width=3
        )

        # Draw the main compass circle outline
        self.canvas.create_oval(
            self.center_x - radius, self.center_y - radius,
            self.center_x + radius, self.center_y + radius,
            outline='black', width=2
        )

        # Draw center dot
        self.canvas.create_oval(
            self.center_x - 3, self.center_y - 3,
            self.center_x + 3, self.center_y + 3,
            fill='black'
        )

        # Cardinal direction labels (inside the white circle)
        directions = [('N', 0), ('E', 90), ('S', 180), ('W', 270)]
        for label, angle_deg in directions:
            angle_rad = math.radians(angle_deg)
            text_x = self.center_x + (radius - 20) * math.sin(angle_rad)
            text_y = self.center_y - (radius - 20) * math.cos(angle_rad)
            self.canvas.create_text(text_x, text_y, text=label, font=('Arial', 16, 'bold'))

        # Compass needle
        self.needle_length = radius - 25
        self.needle = self.canvas.create_line(
            self.center_x, self.center_y,
            self.center_x, self.center_y - self.needle_length,
            arrow=tk.LAST, fill='red', width=3
        )

    def update_direction(self, angle_deg):
        """Update the compass needle direction."""
        angle_rad = math.radians(angle_deg)
        end_x = self.center_x + self.needle_length * math.sin(angle_rad)
        end_y = self.center_y - self.needle_length * math.cos(angle_rad)
        self.canvas.coords(self.needle, self.center_x, self.center_y, end_x, end_y)


class CompassWidget(tk.Frame):
    def __init__(self, parent, width=300, height=300, radius=100, compass_rotation=0, **kwargs):
        super().__init__(parent, **kwargs)
        self.canvas = tk.Canvas(self, width=width, height=height, bg='white', highlightthickness=0)
        self.canvas.pack()

        self.center_x = width // 2
        self.center_y = height // 2
        self.radius = radius
        self.rotation_offset = compass_rotation  # in degrees

        # White background circle
        self.canvas.create_oval(
            self.center_x - radius - 10, self.center_y - radius - 10,
            self.center_x + radius + 10, self.center_y + radius + 10,
            fill='white', outline='black', width=3
        )

        # Compass circle border
        self.canvas.create_oval(
            self.center_x - radius, self.center_y - radius,
            self.center_x + radius, self.center_y + radius,
            outline='black', width=2
        )

        # Center dot
        self.canvas.create_oval(
            self.center_x - 3, self.center_y - 3,
            self.center_x + 3, self.center_y + 3,
            fill='black'
        )

        # Tick marks every 10°
        self._draw_tick_marks()

        # Rotated direction labels
        self._draw_labels()

        # Compass needle
        self.needle_length = radius - 25
        self.needle = self.canvas.create_line(
            self.center_x, self.center_y,
            self.center_x, self.center_y - self.needle_length,
            arrow=tk.LAST, fill='red', width=3
        )

    def _draw_tick_marks(self):
        for deg in range(0, 360, 10):
            angle_rad = math.radians(deg + self.rotation_offset)
            outer_x = self.center_x + self.radius * math.sin(angle_rad)
            outer_y = self.center_y - self.radius * math.cos(angle_rad)

            inner_len = 10 if deg % 90 == 0 else 5  # Long tick for cardinal points
            inner_x = self.center_x + (self.radius - inner_len) * math.sin(angle_rad)
            inner_y = self.center_y - (self.radius - inner_len) * math.cos(angle_rad)

            self.canvas.create_line(inner_x, inner_y, outer_x, outer_y, fill='black', width=1)

    def _draw_labels(self):
        directions = [('S', 0), ('SW', 45), ('W', 90), ('NW', 135),
                      ('N', 180), ('NE', 225), ('E', 270), ('SE', 315)]

        for label, base_angle in directions:
            angle_deg = base_angle + self.rotation_offset
            angle_rad = math.radians(angle_deg)
            text_radius = self.radius - 20

            text_x = self.center_x + text_radius * math.sin(angle_rad)
            text_y = self.center_y - text_radius * math.cos(angle_rad)

            self.canvas.create_text(
                text_x, text_y,
                text=label,
                font=('Arial', 12 if len(label) > 1 else 14, 'bold')
            )

    def update_direction(self, angle_deg):
        """Update the needle direction relative to compass rotation."""
        total_angle = angle_deg + self.rotation_offset + 90
        angle_rad = math.radians(total_angle)

        end_x = self.center_x + self.needle_length * math.sin(angle_rad)
        end_y = self.center_y - self.needle_length * math.cos(angle_rad)

        self.canvas.coords(self.needle, self.center_x, self.center_y, end_x, end_y)