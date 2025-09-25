# This script act as gui for the pseudo pilot. It receives the asterix stream
# and allow the pp to select an aircraft. When an aircraft is selected, it transmits
# the position of the aircraft received from the tba at a certain rate
# -----
# This script has some threads. The first three receive data and update one or more
# global variable and the fourth sends out the location to the audio render pc.
# The threads are:
# 1-> Receive and parse the asterix stream multicast and update the global array aircrafts 
#     with the lat, long and altitude of each
# 2-> Receives the controller pan/tilt position and updates the global variable joystick_pan_heading
# 3-> Receives the head tracking data and updates the global variables ht_yaw ht_pitch ht_roll
#     It also resend the
# 4-> Calculates the relative position of the currently selected aircraft taking into account the 
#     head position and the joystick_pan position sending it to the audio render (if no aircraft
#     is selected it sends out -1). It also saves a log of the variables.

FAKE_ASTERIXXX = False

import tkinter as tk
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
import json
import time
import socket
import threading
import select
import serial
import asterix
import struct
import math
import os
import csv
import random
import argparse
from tkinter import font as tkFont
from functools import partial
from functions import calculate_azimuth, calculate_elevation, CompassWidget
import pickle
import time
from datetime import datetime, timedelta, timezone

ID = 1
# POSIZIONE LIML:
#45°27'6.96750''N   (RADAR 45°26'57.99998'')
#9°16'54.9797''E   (RADAR 9°16'42''E)
#139.72mslm
#HEADING 290

TWR_POSITION = (45.451935417,9.2819388)
TWR_HEADING = 290
TWR_HEIGHT = 0

# RECEIVE
THIS_PC_IP = "192.168.207.171" # IP of this pc
#THIS_PC_IP = "127.0.0.1"
# Asterix CAT62 is received on port:
RECEIVE_ASTERIX_PORT = 43010
# PanTilt controller is received on port:
RECEIVE_PAN_TILT_PORT = 4030

# SEND
POSITION_TRANSMIT_PERIOD = 0.05 # Transmit every 50 msec
AUDIO_RENDER_IP = "192.168.207.172" # IP of audio render pc
#AUDIO_RENDER_IP = "127.0.0.1"
AUDIO_RENDER_AZIMUTH_ELEVATION_PORT = 4010 # Port of audio render pc for azimuth
AUDIO_RENDER_PTT_PORT = 4011 # Port of audio render pc for PP Ptt
LAST_ASTERIX_TRANSMISSION = 0

# GLOBAL VARIABLES
aircrafts = {} # This is a dictionary of the aircrafts. { "CALLSIGN" : [IS_ACTIVE,LAT,LONG,ALTITUDE,LAST_UPDATE,HAS_BEEN_REMOVED] }
ACTIVE_INDEX = 0
LAT_INDEX = 1
LONG_INDEX = 2
ALTITUDE_INDEX = 3
LAST_UPDATE_INDEX = 4
HAS_BEEN_REMOVED_INDEX = 5
selected_aircraft = "-"
joystick_pan_heading = 0 # -180 + 180
kill_threads = False
allow_transmission = False
waiting_for_deactivation = False
dc_widget = None

# --------------------------
# Thread 1 (receive asterix) 
# --------------------------

def t1_receive_asterix_and_update_positions(THIS_PC_IP,RECEIVE_ASTERIX_PORT):
    print("Thread 1 started (receive asterix)")

    global kill_threads
    global aircrafts
    global LAST_ASTERIX_TRANSMISSION
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("0.0.0.0", RECEIVE_ASTERIX_PORT))
    while True:
        if kill_threads:
            break
        ready = select.select([sock], [], [], 1) # wait for 1 second and then go ahead
        if ready[0] and not FAKE_ASTERIXXX:
            data, addr = sock.recvfrom(65507)
            parsed = asterix.parse(data)
            for k in range(len(parsed)):
                category = parsed[k].get("category")
                if category == 62:
                    try:
                        # #XXXX To measure asterix transmission rate
                        CURRENT_ASTERIX_TRANSMISSION = time.time()
                        #print(CURRENT_ASTERIX_TRANSMISSION - LAST_ASTERIX_TRANSMISSION)
                        LAST_ASTERIX_TRANSMISSION = CURRENT_ASTERIX_TRANSMISSION
                        callsign = parsed[k].get("I380").get("ID").get("ACID").get("val").strip()
                        aircrafts[callsign][LAT_INDEX] = parsed[k].get("I105").get("Lat").get("val")
                        aircrafts[callsign][LONG_INDEX] = parsed[k].get("I105").get("Lon").get("val")
                        aircrafts[callsign][ALTITUDE_INDEX] = parsed[k].get("I130").get("Alt").get("val")
                        aircrafts[callsign][LAST_UPDATE_INDEX] = datetime.now(timezone.utc).isoformat().encode()
                    except IndexError:
                        print("The stream is not formatted pretty") 
                    except KeyError:
                        print("The key {} is not present in the dictionary".format(callsign))
                        # add new aircraft to the array
                        aircrafts[callsign] = [0,0,0,0,0,0]
                        aircrafts[callsign][LAT_INDEX] = parsed[k].get("I105").get("Lat").get("val")
                        aircrafts[callsign][LONG_INDEX] = parsed[k].get("I105").get("Lon").get("val")
                        aircrafts[callsign][ALTITUDE_INDEX] = parsed[k].get("I130").get("Alt").get("val")
                        aircrafts[callsign][LAST_UPDATE_INDEX] = datetime.now(timezone.utc).isoformat().encode()
                        print("Added!")
                        load_aircraft_into_buttons()
        elif ready[0] and FAKE_ASTERIXXX:
            data, addr = sock.recvfrom(65507)
            parsed = data.decode("utf-8").split(",")
            try:
                callsign = parsed[0].strip()
                aircrafts[callsign][LAT_INDEX] = float(parsed[1])
                aircrafts[callsign][LONG_INDEX] = float(parsed[2])
                aircrafts[callsign][ALTITUDE_INDEX] = int(parsed[3])
                aircrafts[callsign][LAST_UPDATE_INDEX] = datetime.now(timezone.utc).isoformat().encode()
            except IndexError:
                print("The stream is not formatted pretty") 
            except KeyError:
                print("The key {} is not present in the dictionary".format(callsign))
                # add new aircraft to the array
                aircrafts[callsign] = [0,0,0,0,0,0]
                aircrafts[callsign][LAT_INDEX] = float(parsed[1])
                aircrafts[callsign][LONG_INDEX] = float(parsed[2])
                aircrafts[callsign][ALTITUDE_INDEX] = int(parsed[3])
                aircrafts[callsign][LAST_UPDATE_INDEX] = datetime.now(timezone.utc).isoformat().encode()
                print("Added!")
                load_aircraft_into_buttons()

# ----------------------------
# Thread 3 (transmit location) 
# ----------------------------

def t2_transmit_selected_aircraft_position(AUDIO_RENDER_IP,AUDIO_RENDER_AZIMUTH_ELEVATION_PORT):
    print("Thread 3 started (transmit aircraft position)")

    global kill_threads
    global selected_aircraft
    global aircrafts
    global allow_transmission
    global rel_position_label_var
    global pan_label_var
    global coordinate_label_var
    global height_label_var
    global dc_widget
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
    while True:
        time.sleep(POSITION_TRANSMIT_PERIOD)   
        if kill_threads:
            break
        if allow_transmission:
            if selected_aircraft == "-":
                azimuth = elevation = -1
                rel_position_label_var.set(f"---")
                coordinate_label_var.set(f"---")
                height_label_var.set(f"---")
            else:
                aircraft_lat = aircrafts[selected_aircraft][LAT_INDEX]
                aircraft_lon = aircrafts[selected_aircraft][LONG_INDEX]
                aircraft_height = aircrafts[selected_aircraft][ALTITUDE_INDEX]
                coordinate_label_var.set(f"{aircraft_lat}N {aircraft_lon}E")
                height_label_var.set(f"{aircraft_height} ft")
                azimuth = calculate_azimuth(TWR_POSITION[0], 
                                            TWR_POSITION[1], 
                                            aircraft_lat, 
                                            aircraft_lon, 
                                            heading=TWR_HEADING)
                dc_widget.update_direction(azimuth)
                # We have azimuth that is [0,360] clockwise
                # We have elevation that is [0,90] up
                elevation = calculate_elevation(aircraft_lat, aircraft_lon, aircraft_height, TWR_POSITION[0], TWR_POSITION[1], TWR_HEIGHT)
                rel_position_label_var.set(f"{azimuth}° {elevation}°")
            pan_label_var.set(f"{TWR_HEADING}°")
            # Send relative position to audio render in FUDI format
            sock.sendto(f"{azimuth} {elevation};".encode("utf-8"), (AUDIO_RENDER_IP, AUDIO_RENDER_AZIMUTH_ELEVATION_PORT))

def t3_handle_ptt(AUDIO_RENDER_IP,AUDIO_RENDER_PTT_PORT):
    print("Thread 5 started (activate com)")

    global kill_threads
    global toggle_onair

    last_ptt_click = 0
    last_phone_click = 0

    ser = serial.Serial('/dev/ttyUSB0', 9600, timeout=0.1)  # On Linux/Mac: '/dev/ttyUSB0'
    time.sleep(2)  # Wait for the serial connection to initialize

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    while True:
        if kill_threads:
            break
        line = ser.readline().decode('utf-8').strip()
        if line:
            try:
                value = int(line)
                if value == 0: # If pp is clicking
                    toggle_onair(True)
                    sock.sendto(f"0;".encode("utf-8"), (AUDIO_RENDER_IP, AUDIO_RENDER_PTT_PORT))
                    last_ptt_click = time.time()
                if value == 1: # If apch is clicking
                    toggle_phone(True)
                    sock.sendto(f"1;".encode("utf-8"), (AUDIO_RENDER_IP, AUDIO_RENDER_PTT_PORT))
                    last_phone_click = time.time()
            except ValueError:
                print(f"Ignored non-bool value: {line}")
        else:
            this_time = time.time()
            if this_time - last_ptt_click > 0.25:
                toggle_onair(False)
            if this_time - last_phone_click > 0.25:
                toggle_phone(False)

t1 = threading.Thread(target=t1_receive_asterix_and_update_positions, args=(THIS_PC_IP,RECEIVE_ASTERIX_PORT))
t2 = threading.Thread(target=t2_transmit_selected_aircraft_position, args=(AUDIO_RENDER_IP,AUDIO_RENDER_AZIMUTH_ELEVATION_PORT))
t3 = threading.Thread(target=t3_handle_ptt, args=(AUDIO_RENDER_IP,AUDIO_RENDER_PTT_PORT))

def quit_script():
    global kill_threads
    kill_threads = True
    global root
    t1.join()
    t2.join()
    t3.join()
    root.quit()

# ----------------------------
# GUI styling
# ----------------------------

THEME_NAME = "darkly" # dark
#THEME_NAME = "flatly" # light
WINDOW_WIDTH = 1020
if FAKE_ASTERIXXX:
    WINDOW_HEIGHT = 980
else:
    WINDOW_HEIGHT = 1780
WINDOW_HEIGHT = 1780
FRAME1_WIDTH = 350
FRAME2_WIDTH = 430
FRAME3_WIDTH = 350
SCROLLBAR_HEIGHT = 1780
TREEVIEW_FONT_SIZE = 32
TREEVIEW_ROW_HEIGHT = 48


AIRCRAFT_BUTTON_SIZE = 15
AIRCRAFT_BUTTON_FONT_SIZE = 35
ACTIVE_AIRCRAFT_LABEL_FONT_SIZE = 56

root = ttk.Window(themename=THEME_NAME)
root.geometry(str(WINDOW_WIDTH) + "x" + str(WINDOW_HEIGHT))

root.style.configure('selected_aircraft_label.TLabel', font=('Helvetica', ACTIVE_AIRCRAFT_LABEL_FONT_SIZE))
root.style.configure('danger.TButton', font=('Helvetica', AIRCRAFT_BUTTON_FONT_SIZE), padding=AIRCRAFT_BUTTON_SIZE)
root.style.configure('secondary.TButton', font=('Helvetica', AIRCRAFT_BUTTON_FONT_SIZE), padding=AIRCRAFT_BUTTON_SIZE)

frame0 = ttk.Frame(root, width=FRAME1_WIDTH, height=WINDOW_HEIGHT) 
frame0.grid(row=0, column=0)
frame0.pack_propagate(0)

frame1 = ttk.Frame(root, width=FRAME2_WIDTH, height=WINDOW_HEIGHT) 
frame1.grid(row=0, column=1)
frame1.pack_propagate(0)

frame2 = ttk.Frame(root, width=FRAME3_WIDTH, height=WINDOW_HEIGHT) 
frame2.grid(row=0, column=2)
frame2.pack_propagate(0)

subframe2 = ttk.Frame(frame2, width=200, height=SCROLLBAR_HEIGHT) 
subframe2.pack(pady=2,padx=20,anchor=tk.N)
subframe2.pack_propagate(0)

aircraft_buttons = []

# Active aircrafts are aircrafts that are in the center

def select_aircraft(callsign):
    global selected_aircraft
    global waiting_for_deactivation
    if waiting_for_deactivation:
        #if selected_aircraft == callsign:
        #    pass
        #else: questo qui sotto era tutto tabbato sotto l'else
        aircrafts[callsign][ACTIVE_INDEX] = 0
        aircrafts[callsign][HAS_BEEN_REMOVED_INDEX] = 1
        selected_aircraft = "-"
        # Uncomment down here to allow only 1 deactivation at a time
        remove_button.config(style='primary.TButton')
        select_to_remove_label.config(text = "")
        waiting_for_deactivation = False
        update_buttons()
        root.update()
    else:
        if selected_aircraft == callsign:
            selected_aircraft = "-"
        else:
            selected_aircraft = callsign
        selected_aircraft_label.config(text = selected_aircraft)
    selected_aircraft_label.config(text = selected_aircraft)
    update_buttons()

def make_selected_active():
    sel = treeview.selection()
    if sel == "":
        return
    for s in sel:
        aircrafts[s][ACTIVE_INDEX] = 1
        aircrafts[s][HAS_BEEN_REMOVED_INDEX] = 0
    treeview.selection_remove(treeview.selection())
    update_buttons()
    root.update()

def make_all_active():
    global aircrafts
    for a in aircrafts.keys():
        if aircrafts[a][HAS_BEEN_REMOVED_INDEX] == 0:
            aircrafts[a][ACTIVE_INDEX] = 1
    update_buttons()
    root.update()

def delete_selected():
    sel = treeview.focus()
    sel = treeview.selection()
    if sel == "":
        return
    for s in sel:
        aircrafts.pop(s)
    if sel == "":
        return
    treeview.selection_remove(treeview.selection())
    update_buttons()
    root.update()

def toggle_select_deactive():
    global waiting_for_deactivation
    global selected_aircraft
    #if selected_aircraft == "-": questo qua sotto era tutto tabbatoi per if
    waiting_for_deactivation = not waiting_for_deactivation
    if waiting_for_deactivation:
        select_to_remove_label.config(text = "Select A/C to remove")
        remove_button.config(style='warning.TButton')
    else:
        remove_button.config(style='primary.TButton')
        select_to_remove_label.config(text = "")

def remove_buttons():
    for b in aircraft_buttons:
        b.pack_forget()

def update_buttons():
    treeview.delete(*treeview.get_children())
    for b in aircraft_buttons:
        b.pack_forget()
    for b in aircraft_buttons:
        if aircrafts[b.cget("text")][ACTIVE_INDEX] == 1:
            # highlight the selected aircraft
            if b.cget("text") == selected_aircraft:
                b.config(style='danger.TButton')
            # normal color for the other active aircrafts
            else:
                b.config(style='secondary.TButton')
            b.pack(side = ttk.TOP, fill = ttk.BOTH, pady=(5, 5))
            treeview.insert("", "end", b.cget("text"),text=b.cget("text"), tags=("green",))
        # insert all aircraft in the scroll menu
        else:
            if aircrafts[b.cget("text")][HAS_BEEN_REMOVED_INDEX] == 1:
                treeview.insert("", "end", b.cget("text"),text=b.cget("text"), tags=("grey",))
            else:
                treeview.insert("", "end", b.cget("text"),text=b.cget("text"), tags=("white",))

    scrollbar.configure(command=treeview.yview)

selected_aircraft_label = ttk.Label(frame0, text="-",style='selected_aircraft_label.TLabel')
selected_aircraft_label.pack(side = ttk.TOP, pady=(50, 10)) #, anchor=N

def on_transmission_toggle():
    global allow_transmission
    allow_transmission = transmission_var.get()

quit_button = ttk.Button(frame0, text="quit",command=quit_script,style='primary.TButton')
quit_button.pack(side = ttk.BOTTOM)

transmission_var = ttk.IntVar()
allow_transmit_toggle = ttk.Checkbutton(frame0, text=f"Start ID: {ID}", variable=transmission_var, 
                             onvalue=True, offvalue=False, command=on_transmission_toggle,
                             bootstyle="round-toggle", padding=(0,0,0,20))
allow_transmit_toggle.pack(side = ttk.BOTTOM)

onair_name_label = tk.Label( frame0, text="ON AIR!", font=("Helvetica", 48, "bold"), )
onair_name_label.pack()
onair_name_label.config(pady=20)
onair_name_label.config(padx=20)
onair_name_label.config(fg="white")
onair_name_label.config(bg="red")
onair_name_label.pack_forget()

phone_name_label = tk.Label( frame0, text="APCH", font=("Helvetica", 48, "bold"), )
phone_name_label.pack()
phone_name_label.config(pady=20)
phone_name_label.config(padx=20)
phone_name_label.config(fg="white")
phone_name_label.config(bg="green")
phone_name_label.pack_forget()

def toggle_onair(onoff):
    if onoff:
        onair_name_label.pack()
    else:
        onair_name_label.pack_forget()

def toggle_phone(onoff):
    if onoff:
        phone_name_label.pack()
    else:
        phone_name_label.pack_forget()

dc_widget = CompassWidget(frame0, width=300, height=300, radius=70, compass_rotation=290)
dc_widget.pack()

pan_label_var = ttk.StringVar()
pan_label_var.set("-")
pan_label = ttk.Label( frame0, textvariable=pan_label_var, font=("Helvetica", 14, "bold"), padding=(0,0,0,20))
pan_label.pack(side = ttk.BOTTOM)
pan_name_label = ttk.Label( frame0, text="Pan:")
pan_name_label.pack(side = ttk.BOTTOM)

height_label_var = ttk.StringVar()
height_label_var.set("-")
height_label = ttk.Label( frame0, textvariable=height_label_var, font=("Helvetica", 14, "bold"))
height_label.pack(side = ttk.BOTTOM)
height_name_label = ttk.Label( frame0, text="Height:")
height_name_label.pack(side = ttk.BOTTOM)

coordinate_label_var = ttk.StringVar()
coordinate_label_var.set("-")
coordinate_label = ttk.Label( frame0, textvariable=coordinate_label_var, font=("Helvetica", 14, "bold"))
coordinate_label.pack(side = ttk.BOTTOM)
coordinate_name_label = ttk.Label( frame0, text="Position:")
coordinate_name_label.pack(side = ttk.BOTTOM)

rel_position_label_var = ttk.StringVar()
rel_position_label_var.set("-")
rel_position_label = ttk.Label( frame0, textvariable=rel_position_label_var, font=("Helvetica", 14, "bold"))
rel_position_label.pack(side = ttk.BOTTOM)
rel_name_position_label = ttk.Label( frame0, text="Relative position:")
rel_name_position_label.pack(side = ttk.BOTTOM)

select_to_remove_label = ttk.Label(subframe2, text="")
select_to_remove_label.pack(side = ttk.TOP, pady=(10, 10)) #, anchor=N

remove_button = ttk.Button(subframe2, text="remove",command=toggle_select_deactive,style='primary.TButton')
remove_button.pack(side = ttk.TOP, fill = ttk.BOTH,pady=(10, 0),ipady=10)

add_button = ttk.Button(subframe2, text="add",command=make_selected_active,style='primary.TButton')
add_button.pack(side = ttk.TOP, fill = ttk.BOTH,pady=(10, 0),ipady=10)

add_all_button = ttk.Button(subframe2, text="add all",command=make_all_active,style='primary.TButton')
add_all_button.pack(side = ttk.TOP, fill = ttk.BOTH,pady=(10, 10),ipady=10)

# Configure Treeview style
custom_font_tw = ttk.font.Font(family="Helvetica", size=TREEVIEW_FONT_SIZE)
style_tw = ttk.Style()
style_tw.configure("Treeview", font=custom_font_tw, rowheight=TREEVIEW_ROW_HEIGHT)  # Font for rows

# Insert deactivated aircraft section
scrollbar = ttk.Scrollbar(subframe2)
treeview = ttk.Treeview(subframe2, yscrollcommand=scrollbar.set, show="tree",  selectmode='extended')
scrollbar.configure(command=treeview.yview,bootstyle="round")
scrollbar.pack(side="right", fill="y")
treeview.pack(side="left", fill="both", expand=True)

treeview.tag_configure("grey", foreground="grey")
treeview.tag_configure("white", foreground="white")
treeview.tag_configure("green", foreground="green")

def load_aircraft_into_buttons():
    global aircrafts
    global aircraft_buttons
    remove_buttons()
    aircraft_buttons = []
    for a in sorted(aircrafts.keys()):
        aircraft_buttons.append(
            ttk.Button(frame1, text=a, command= partial(select_aircraft, a))
        )
    update_buttons()

load_aircraft_into_buttons()

t1.start()
t2.start()
t3.start()

root.geometry(f"{root.winfo_screenwidth()}x{root.winfo_screenheight()}")

root.mainloop()
