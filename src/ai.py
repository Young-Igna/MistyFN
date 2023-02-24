import ctypes
import json
import math
import os
import threading
import time

import PySimpleGUI as sg
import cv2
import mss
import numpy as np
import torch
from pynput import keyboard

from msg_utils import show_error, show_warning

PUL = ctypes.POINTER(ctypes.c_ulong)


class KeyBdInput(ctypes.Structure):
    _fields_ = [("wVk", ctypes.c_ushort),
                ("wScan", ctypes.c_ushort),
                ("dwFlags", ctypes.c_ulong),
                ("time", ctypes.c_ulong),
                ("dwExtraInfo", PUL)]


class HardwareInput(ctypes.Structure):
    _fields_ = [("uMsg", ctypes.c_ulong),
                ("wParamL", ctypes.c_short),
                ("wParamH", ctypes.c_ushort)]


class MouseInput(ctypes.Structure):
    _fields_ = [("dx", ctypes.c_long),
                ("dy", ctypes.c_long),
                ("mouseData", ctypes.c_ulong),
                ("dwFlags", ctypes.c_ulong),
                ("time", ctypes.c_ulong),
                ("dwExtraInfo", PUL)]


class Input_I(ctypes.Union):
    _fields_ = [("ki", KeyBdInput),
                ("mi", MouseInput),
                ("hi", HardwareInput)]


class Input(ctypes.Structure):
    _fields_ = [("type", ctypes.c_ulong),
                ("ii", Input_I)]


class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


class AI:
    extra = ctypes.c_ulong(0)
    ii_ = Input_I()
    screen = mss.mss()

    enabled = False
    config = None

    half_screen_width = ctypes.windll.user32.GetSystemMetrics(0) / 2
    half_screen_height = ctypes.windll.user32.GetSystemMetrics(1) / 2

    layout = []
    window = None

    def __init__(self, debug=False):
        self.debug = debug
        if os.path.exists("src/configs/config.json"):
            with open("src/configs/config.json", "r") as f:
                self.config = json.load(f)

        if self.config is None or "xysens" not in self.config or "scopesens" not in self.config:
            show_error(
                "A configuration error was detected.\nReconfigure sensitivity by selecting Sensitivity Setup in main window.")

        layout = [
            [sg.VPush()],
            [sg.Push(), sg.Text("Downloading AI model...", justification="center"),
             sg.Push()],
            [sg.VPush()]
        ]
        window = sg.Window("Downloading...", layout, finalize=True, icon="src/icon.ico")
        window.set_min_size((300, 1))
        window.read(timeout=1)
        if self.debug:
            self.model = torch.hub.load('MistyAI/MistyFN-YOLOv5', 'custom', path='src/best.pt', force_reload=False)
        else:
            self.model = torch.hub.load('MistyAI/MistyFN-YOLOv5', 'custom', path='src/best.pt', force_reload=True)
        window.close()
        if not torch.cuda.is_available():
            show_warning("CUDA acceleration is not available, performance will be affected.")

        # if config.json doesnt include any of values: box_constant, trigger_fov, aim_fov, aim_speed, confidence then add them with default values
        if "box_constant" not in self.config:
            self.config["box_constant"] = 660
        if "trigger_fov" not in self.config:
            self.config["trigger_fov"] = 25
        if "aim_fov" not in self.config:
            self.config["aim_fov"] = 90
        if "aim_speed" not in self.config:
            self.config["aim_speed"] = 33
        if "confidence" not in self.config:
            self.config["confidence"] = 0.7
        if "visualize" not in self.config:
            self.config["visualize"] = False
        # if "always_on_top" not in self.config:
        #     self.config["always_on_top"] = True
        if "keybind" not in self.config:
            self.config["keybind"] = "Key.caps_lock"
        if "keybind_logic" not in self.config:
            self.config["keybind_logic"] = "Toggle"

        self.model.conf = self.config["confidence"]
        self.model.iou = 0.75

        self.detection_box = {'left': int(self.half_screen_width - self.config["box_constant"] // 2),
                              # x1 coord (for top-left corner of the box)
                              'top': int(self.half_screen_height - self.config["box_constant"] // 2),
                              # y1 coord (for top-left corner of the box)
                              'width': int(self.config["box_constant"]),  # width of the box
                              'height': int(self.config["box_constant"])}  # height of the box

    def on_release(self, key):
        try:
            key = str(key).replace("'", "")
            if self.config["keybind_logic"] == "Toggle":
                if key == self.config["keybind"]:
                    self.toggle()
            if self.config["keybind_logic"] == "Hold":
                if key == self.config["keybind"]:
                    self.enabled = False
                    self.window["status"].update("Status: Disabled")

        except NameError:
            pass

    def on_press(self, key):
        try:
            # check if keybind inputtext is focused
            if self.window.FindElementWithFocus() is not None:
                if self.window.FindElementWithFocus().key == "keybind":
                    self.config["keybind"] = str(key).replace("'", "")
                    displayKey = str(key).replace("'", "").replace("Key.", "").replace("_", " ").upper()
                    self.window["keybind"].update(displayKey)
            if self.config["keybind_logic"] == "Hold":
                key = str(key).replace("'", "")
                if key == self.config["keybind"]:
                    self.enabled = True
                    self.window["status"].update("Status: Enabled")
        except NameError:
            pass

    def toggle(self):
        self.enabled = not self.enabled
        # get status text from main window and change it to "Status: Enabled" or "Status: Disabled"
        self.window["status"].update("Status: Enabled" if self.enabled else "Status: Disabled")

    def in_trigger_fov(self, x, y):
        return math.sqrt((x - self.half_screen_width) ** 2 + (y - self.half_screen_height) ** 2) < self.config[
            "trigger_fov"]

    def in_aim_fov(self, x, y):
        return math.sqrt((x - self.half_screen_width) ** 2 + (y - self.half_screen_height) ** 2) < self.config[
            "aim_fov"]

    def interpolate(self, x, y):
        relative_x = (x - self.half_screen_width) * self.config["xysens"] / self.config["aim_speed"]
        relative_y = (y - self.half_screen_height) * self.config["xysens"] / self.config["aim_speed"]

        distance = int(math.dist((0, 0), (relative_x, relative_y)))
        if distance == 0:
            return

        unit_x = relative_x / distance * self.config["aim_speed"]
        unit_y = relative_y / distance * self.config["aim_speed"]

        current_x = current_y = total_x = total_y = 0
        for step in range(distance):
            total_x += current_x
            total_y += current_y
            current_x = round(unit_x * step - total_x)
            current_y = round(unit_y * step - total_y)
            yield current_x, current_y

    def detect_players(self, frame):
        results = self.model(frame)
        # make json object for all players
        players = []
        for *box, conf, cls in results.xyxy[0]:
            x1y1 = [int(x.item()) for x in box[:2]]
            x2y2 = [int(x.item()) for x in box[2:]]
            x1, y1, x2, y2, conf = *x1y1, *x2y2, conf.item()
            height = y2 - y1
            relative_head_X, relative_head_Y = int((x1 + x2) / 2), int((y1 + y2) / 2 - height / 3.2)
            own_player = x1 < 15 or (x1 < self.config["box_constant"] / 5 and y2 > self.config["box_constant"] / 1.2)
            # make json object for player with all values
            player = {
                "x1": x1,
                "y1": y1,
                "x2": x2,
                "y2": y2,
                "conf": conf,
                "cls": cls,
                "height": height,
                "relative_head_X": relative_head_X,
                "relative_head_Y": relative_head_Y,
                "own_player": own_player
            }
            # add player to players list
            players.append(player)
        return players

    def get_closest_player(self, players):
        closest_player = None
        for player in players:
            if player["own_player"]:
                continue

            relative_head_X, relative_head_Y = player["relative_head_X"], player["relative_head_Y"]

            crosshair_dist = math.dist((relative_head_X, relative_head_Y),
                                       (self.config["box_constant"] / 2, self.config["box_constant"] / 2))

            if not closest_player:
                closest_player = player
            elif crosshair_dist < math.dist(
                    (closest_player["relative_head_X"], closest_player["relative_head_Y"]),
                    (self.config["box_constant"] / 2, self.config["box_constant"] / 2)):
                closest_player = player

        return closest_player

    def aim(self, x, y):
        self.currently_aiming = True
        for rel_x, rel_y in self.interpolate(x, y):
            if rel_x == 0 and rel_y == 0:
                continue
            if self.in_trigger_fov(x, y):
                break
            if not self.enabled:
                break
            if time.perf_counter() * 1000 - self.last_moved_time > 2:
                self.ii_.mi = MouseInput(rel_x, rel_y, 0, 0x0001, 0, ctypes.pointer(self.extra))
                input_obj = Input(ctypes.c_ulong(0), self.ii_)
                ctypes.windll.user32.SendInput(1, ctypes.byref(input_obj), ctypes.sizeof(input_obj))
                self.last_moved_time = time.perf_counter() * 1000
            else:
                time.sleep(2 / 1000)
                continue
        self.currently_aiming = False

    def shoot(self):
        self.currently_shooting = True
        if time.perf_counter() * 1000 - self.last_shooted_time > 20:
            left_click_pressed = ctypes.windll.user32.GetKeyState(0x01) & 0x8000
            if not left_click_pressed:
                self.ii_.mi = MouseInput(0, 0, 0, 0x0002, 0, ctypes.pointer(self.extra))
                x = Input(ctypes.c_ulong(0), self.ii_)
                ctypes.windll.user32.SendInput(1, ctypes.pointer(x), ctypes.sizeof(x))
                self.ii_.mi = MouseInput(0, 0, 0, 0x0004, 0, ctypes.pointer(self.extra))
                x = Input(ctypes.c_ulong(0), self.ii_)
                ctypes.windll.user32.SendInput(1, ctypes.pointer(x), ctypes.sizeof(x))
                self.last_shooted_time = time.perf_counter() * 1000
        else:
            time.sleep(20 / 1000)
        self.currently_shooting = False

    def handle_main_logic(self):
        self.lastResult = 0
        self.last_moved_time = 0
        self.last_shooted_time = 0
        self.currently_aiming = False
        self.currently_shooting = False
        while True:
            frame = np.array(self.screen.grab(self.detection_box))
            players = self.detect_players(frame)
            closest_player = self.get_closest_player(players)
            if self.enabled:
                threading.Thread(target=self.handle_misty_logic, args=(closest_player,)).start()
            if self.config["visualize"]:
                # threading.Thread(target=self.update_visualizer, args=(frame, players, closest_player)).start()
                for player in players:
                    # get all values from player
                    x1, y1, x2, y2, conf, cls, height, relative_head_X, relative_head_Y, own_player = player.values()
                    x1y1 = (x1, y1)
                    x2y2 = (x2, y2)
                    absolute_head_X, absolute_head_Y = relative_head_X + self.detection_box["left"], relative_head_Y + \
                                                       self.detection_box["top"]
                    if not own_player:
                        cv2.rectangle(frame, x1y1, x2y2, (0, 0, 255), 2)
                        cv2.putText(frame, f"{int(conf * 100)}%", x1y1, cv2.FONT_HERSHEY_DUPLEX, 0.5, (0, 0, 255), 2)
                        # check if current player is closest player
                        if player == closest_player:
                            if self.in_trigger_fov(absolute_head_X, absolute_head_Y):
                                cv2.circle(frame, (relative_head_X, relative_head_Y), 5, (0, 255, 0), -1)
                            elif self.in_aim_fov(absolute_head_X, absolute_head_Y):
                                cv2.circle(frame, (relative_head_X, relative_head_Y), 5, (255, 0, 0), -1)
                                cv2.line(frame,
                                         (int(self.config["box_constant"] / 2), int(self.config["box_constant"] / 2)),
                                         (relative_head_X, relative_head_Y), (255, 0, 0), 2)
                            else:
                                cv2.line(frame,
                                         (int(self.config["box_constant"] / 2), int(self.config["box_constant"] / 2)),
                                         (relative_head_X, relative_head_Y), (0, 0, 255), 2)
                                cv2.circle(frame, (relative_head_X, relative_head_Y), 5, (0, 0, 255), -1)
                        else:
                            cv2.circle(frame, (relative_head_X, relative_head_Y), 5, (0, 0, 255), -1)

                    else:
                        cv2.rectangle(frame, x1y1, x2y2, (0, 255, 0), 2)
                        cv2.putText(frame, f"{int(conf * 100)}% (OWN PLAYER)", x1y1, cv2.FONT_HERSHEY_DUPLEX, 0.5,
                                    (0, 255, 0),
                                    2)
                # make circle of trigger fov of green color and circle of aimbot fov of blue color
                cv2.circle(frame, (int(self.config["box_constant"] / 2), int(self.config["box_constant"] / 2)),
                           int(self.config["trigger_fov"]), (0, 255, 0), 2)
                cv2.circle(frame, (int(self.config["box_constant"] / 2), int(self.config["box_constant"] / 2)),
                           int(self.config["aim_fov"]), (255, 0, 0), 2)

                cv2.imshow("MistyFN - Visualizer", frame)
                # if self.config["always_on_top"]:
                #     cv2.setWindowProperty("MistyFN - Visualizer", cv2.WND_PROP_TOPMOST, 1)
                # else:
                #     cv2.setWindowProperty("MistyFN - Visualizer", cv2.WND_PROP_TOPMOST, 0)
                if cv2.waitKey(1) & 0xFF == ord('0'):
                    break
            else:
                cv2.destroyAllWindows()
            # if self.config["always_on_top"]:
            #     # make main PySimplegUI window always on top
            #     self.window.TKroot.attributes("-topmost", True)
            # else:
            #     self.window.TKroot.attributes("-topmost", False)

    def handle_misty_logic(self, closest_player):
        if closest_player:
            relative_head_X, relative_head_Y = closest_player["relative_head_X"], closest_player[
                "relative_head_Y"]
            absolute_head_X, absolute_head_Y = relative_head_X + self.detection_box["left"], relative_head_Y + \
                                               self.detection_box["top"]
            if self.in_trigger_fov(absolute_head_X, absolute_head_Y):
                if not self.currently_shooting:
                    threading.Thread(target=self.shoot).start()
            if self.in_aim_fov(absolute_head_X, absolute_head_Y):
                if not self.currently_aiming:
                    threading.Thread(target=self.aim, args=(absolute_head_X, absolute_head_Y)).start()

    def start(self):
        # make layout with all values and sliders to them, make them with key, enable_events and description text next to them
        displayKey = str(self.config["keybind"]).replace("Key.", "").replace("_", " ").upper()
        self.layout = [
            [sg.VPush()],
            [sg.VPush()],
            [sg.VPush()],
            [sg.Push(), sg.Text("Box Constant"),
             sg.Slider(range=((self.half_screen_height / 10) * 4, self.half_screen_height * 2),
                       default_value=self.config["box_constant"], key="box_constant", enable_events=True,
                       orientation="horizontal"), sg.Push()],
            [sg.Push(), sg.Text("Trigger FOV"),
             sg.Slider(range=(1, (self.half_screen_height / 10) * 3), default_value=self.config["trigger_fov"],
                       key="trigger_fov", enable_events=True, orientation="horizontal"), sg.Push()],
            [sg.Push(), sg.Text("Aim FOV"),
             sg.Slider(range=(1, (self.half_screen_height / 10) * 3), default_value=self.config["aim_fov"],
                       key="aim_fov", enable_events=True, orientation="horizontal"), sg.Push()],
            [sg.Push(), sg.Text("Aim Speed"),
             sg.Slider(range=(5, 50), default_value=self.config["aim_speed"], key="aim_speed", enable_events=True,
                       orientation="horizontal"), sg.Push()],
            [sg.Push(), sg.Text("Confidence"),
             sg.Slider(range=(0.5, 0.9), resolution=0.01, default_value=self.config["confidence"], key="confidence",
                       enable_events=True, orientation="horizontal"), sg.Push()],
            # margin between sliders and buttons
            [sg.VPush()],
            [sg.VPush()],
            [sg.VPush()],
            # add checkbox with visualize text on left and save button on right
            [sg.Push(), sg.Checkbox("Visualize", key="visualize", default=self.config["visualize"], enable_events=True),
             sg.Push(),
             sg.Button("Save Config", key="save_cfg", enable_events=True), sg.Push()],
            # add checkbox of always on top
            # [sg.Push(), sg.Checkbox("Always On Top", key="always_on_top", default=self.config["always_on_top"],
            #                         enable_events=True), sg.Push()],
            # [sg.VPush()],
            # [sg.VPush()],
            # [sg.VPush()],

            # add text with status of ai, if true then "AI: Enabled" else "AI: Disabled"
            [sg.Push(), sg.Text("Status: Enabled" if self.enabled else "Status: Disabled", key="status"),
             sg.Push()],
            [sg.Push(), sg.Text("Keybind:"), sg.Push()],
            [sg.Push(), sg.InputText(key="keybind", default_text=displayKey, justification="center", size=(20, 10)),
             sg.Push()],
            # add switch to set hold or toggle mode with one entry in config
            [sg.Push(), sg.Text("Keybind Logic:"), sg.Push()],
            [sg.Push(),
             sg.Combo(["Toggle", "Hold"], key="keybind_logic", default_value=self.config["keybind_logic"],
                      enable_events=True), sg.Push()],
            [sg.VPush()],
            [sg.VPush()],
            [sg.VPush()]

        ]
        if self.debug:
            self.layout = [
                [sg.VPush()],
                [sg.VPush()],
                [sg.VPush()],
                [sg.Push(),
                 sg.Text("Running in Debug mode.\nSliders are unlocked to unsafe values.", justification="center"),
                 sg.Push()],
                [sg.VPush()],
                [sg.VPush()],
                [sg.VPush()],
                [sg.Push(), sg.Text("Box Constant"),
                 sg.Slider(range=(4, self.half_screen_height * 2), default_value=self.config["box_constant"],
                           key="box_constant", enable_events=True, orientation="horizontal"), sg.Push()],
                [sg.Push(), sg.Text("Trigger FOV"),
                 sg.Slider(range=(1, self.half_screen_height * 2), default_value=self.config["trigger_fov"],
                           key="trigger_fov", enable_events=True, orientation="horizontal"), sg.Push()],
                [sg.Push(), sg.Text("Aim FOV"),
                 sg.Slider(range=(1, self.half_screen_height * 2), default_value=self.config["aim_fov"],
                           key="aim_fov", enable_events=True, orientation="horizontal"), sg.Push()],
                [sg.Push(), sg.Text("Aim Speed"),
                 sg.Slider(range=(0, 100), default_value=self.config["aim_speed"], key="aim_speed", enable_events=True,
                           orientation="horizontal"), sg.Push()],
                [sg.Push(), sg.Text("Confidence"),
                 sg.Slider(range=(0, 1), resolution=0.01, default_value=self.config["confidence"], key="confidence",
                           enable_events=True, orientation="horizontal"), sg.Push()],
                # margin between sliders and buttons
                [sg.VPush()],
                [sg.VPush()],
                [sg.VPush()],
                # add checkbox with visualize text on left and save button on right
                [sg.Push(),
                 sg.Checkbox("Visualize", key="visualize", default=self.config["visualize"], enable_events=True),
                 sg.Push(),
                 sg.Button("Save Config", key="save_cfg", enable_events=True), sg.Push()],
                # add checkbox of always on top
                # [sg.Push(), sg.Checkbox("Always On Top", key="always_on_top", default=self.config["always_on_top"],
                #                         enable_events=True), sg.Push()],
                # [sg.VPush()],
                # [sg.VPush()],
                # [sg.VPush()],
                # add text with status of ai, if true then "AI: Enabled" else "AI: Disabled"
                [sg.Push(), sg.Text("Status: Enabled" if self.enabled else "Status: Disabled", key="status"),
                 sg.Push()],
                [sg.Push(), sg.Text("Keybind:"), sg.Push()],
                [sg.Push(), sg.InputText(key="keybind", default_text=displayKey, justification="center", size=(20, 10)),
                 sg.Push()],
                # add switch to set hold or toggle mode with one entry in config
                [sg.Push(), sg.Text("Keybind Logic:"), sg.Push()],
                [sg.Push(),
                 sg.Combo(["Toggle", "Hold"], key="keybind_logic", default_value=self.config["keybind_logic"],
                          enable_events=True), sg.Push()],
                [sg.VPush()],
                [sg.VPush()],
                [sg.VPush()]
            ]

        self.window = sg.Window("MistyFN", self.layout, finalize=True, icon="src/icon.ico")
        self.window.set_min_size((300, 1))

        keyboard.Listener(on_release=self.on_release, on_press=self.on_press).start()

        threading.Thread(target=self.handle_main_logic).start()

        while True:
            event, values = self.window.read()

            if event == sg.WIN_CLOSED:
                self.enabled = False
                self.screen.close()
                os._exit(0)
                break
            self.config["box_constant"] = values["box_constant"]
            self.config["trigger_fov"] = values["trigger_fov"]
            self.config["aim_fov"] = values["aim_fov"]
            self.config["aim_speed"] = values["aim_speed"]
            self.config["confidence"] = values["confidence"]
            self.config["visualize"] = values["visualize"]
            self.detection_box = {'left': int(self.half_screen_width - self.config["box_constant"] // 2),
                                  # x1 coord (for top-left corner of the box)
                                  'top': int(self.half_screen_height - self.config["box_constant"] // 2),
                                  # y1 coord (for top-left corner of the box)
                                  'width': int(self.config["box_constant"]),  # width of the box
                                  'height': int(self.config["box_constant"])}  # height of the box
            self.model.conf = self.config["confidence"]
            # self.config["always_on_top"] = values["always_on_top"]
            self.config["keybind_logic"] = values["keybind_logic"]

            if event == "save_cfg":
                if self.debug:
                    show_warning("You can't save config in debug mode!")
                else:
                    with open("src/configs/config.json", "w") as f:
                        json.dump(self.config, f)


if __name__ == '__main__':
    show_error("Start MistyFN with start.vbs in root directory!")
