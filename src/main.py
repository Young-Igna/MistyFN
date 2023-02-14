import json
import os
import webbrowser

import PySimpleGUI as sg
import requests

import msg_utils
from ai import AI

sg.theme("DarkGrey5")

version = "1.0.0b"


def sensitivity_setup():
    # layout with 1 slider of X/Y sensitivity and 1 slider of targeting/scope sensitivity
    # range from 1.0 to 100.0 with 0.1 increments

    # get current values of xysens and scopesens from config.json
    if os.path.exists("src/configs/config.json"):
        with open("src/configs/config.json", "r") as f:
            data = json.load(f)
        if "xysens" not in data:
            xysens = 50.0
        else:
            xysens = data["xysens"]
        if "scopesens" not in data:
            scopesens = 50.0
        else:
            scopesens = data["scopesens"]
    else:
        xysens = 50.0
        scopesens = 50.0

    layout = [
        [sg.VPush()],
        [sg.Push(), sg.Text("Important notes:"), sg.Push()],
        [sg.Push(), sg.Text("X and Y sensitivity should be the same in game,"), sg.Push()],
        [sg.Push(), sg.Text("Scope and Targeting sensitivity should be the same in game,"), sg.Push()],
        [sg.Push(), sg.Text("Set sliders to values that you have in game."), sg.Push()],
        [sg.Push(),
         sg.Slider(range=(1.0, 100.0), default_value=xysens, resolution=0.1, orientation="horizontal", key="xysens"),
         sg.Push()],
        [sg.Push(), sg.Text("X/Y Sensitivity"), sg.Push()],
        [sg.Push(),
         sg.Slider(range=(1.0, 100.0), default_value=scopesens, resolution=0.1, orientation="horizontal",
                   key="scopesens"),
         sg.Push()],
        [sg.Push(), sg.Text("Scope/Targeting Sensitivity"), sg.Push()],
        [sg.Push(), sg.Button("Save", key="save", enable_events=True), sg.Push()],
        # add 2 notes that X and Y sens should be the same in game as well as scope and targeting sens should be the same in game
        # and that the sliders are for the game
        [sg.VPush()]
    ]

    window = sg.Window("Sensitivity Setup", layout, finalize=True, icon="src/icon.ico")

    while True:
        event, values = window.read()
        if event == sg.WIN_CLOSED:
            window.close()
            main()
            break
        if event == "save":
            # if config.json doesnt exist, create it
            if not os.path.exists("configs/config.json"):
                with open("src/configs/config.json", "w") as f:
                    json.dump({"xysens": values["xysens"], "scopesens": values["scopesens"]}, f)
            # if it does exist, load it and update the values
            else:
                with open("src/configs/config.json", "r") as f:
                    data = json.load(f)
                data["xysens"] = values["xysens"]
                data["scopesens"] = values["scopesens"]
                with open("src/configs/config.json", "w") as f:
                    json.dump(data, f)
            window.close()
            main()
            break


def check_for_update():
    try:
        # make get request to github api to get latest release
        r = requests.get("https://api.github.com/repos/MistyAI/MistyFN/releases/latest")
        # get the tag_name from the response
        latest_release = r.json()["tag_name"]
        # if the latest release is not the same as the current version, return tag name and description in json format
        if latest_release != version:
            description = r.json()["body"]
            # replace every \r with nothing
            description = description.replace("\r", "")
            return {"tag_name": latest_release, "description": description}
        # if the latest release is the same as the current version, return None
        else:
            return None
    except:
        msg_utils.show_warning(
            "Failed to retrieve information about new update.\nThis will not affect functionality of MistyFN, except that you will not receive information about new update.")


def main():
    layout = [
        [sg.VPush()],
        [sg.Push(), sg.Button("Start", key="start", enable_events=True, disabled=True), sg.Push()],
        [sg.Push(), sg.Button("Sensitivity Setup", key="sens", enable_events=True), sg.Push()],
        [sg.Push(), sg.Text(version), sg.Push()],
        [sg.VPush()]
    ]

    window = sg.Window("MistyFN", layout, finalize=True, icon="src/icon.ico")

    # if config.json does exist, enable the start button
    if os.path.exists("src/configs/config.json"):
        layout[1][1].update(disabled=False)

    while True:
        event, values = window.read()
        if event == sg.WIN_CLOSED:
            break
        if event == "start":
            window.close()
            FearAI = AI()
            FearAI.start()
            break
        if event == "sens":
            window.close()
            sensitivity_setup()
            break


if __name__ == "__main__":
    update_info = check_for_update()
    if update_info is not None:
        response = msg_utils.show_custom_prompt(
            f"Version {update_info['tag_name']} is available!\n\n{update_info['description']}\n",
            "Update Available", "Download on GitHub")
        if response:
            webbrowser.open(f"https://github.com/MistyAI/MistyFN/releases/tag/{update_info['tag_name']}")
            exit()
    main()
