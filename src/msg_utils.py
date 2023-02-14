import PySimpleGUI as sg


def show_error(msg):
    layout = [
        [sg.VPush()],
        [sg.Push(), sg.Text(msg, justification="center"),
         sg.Push()],
        [sg.Push(), sg.Button("OK", key="Exit", enable_events=True), sg.Push()],
        [sg.VPush()]
    ]
    window = sg.Window("Error", layout, finalize=True, icon="src/icon.ico")
    window.set_min_size((300, 1))
    while True:
        event, values = window.read()
        if event == sg.WIN_CLOSED:
            exit()
            break
        if event == "Exit":
            window.close()
            exit()
            break


def show_success(msg):
    layout = [
        [sg.VPush()],
        [sg.Push(), sg.Text(msg, justification="center"),
         sg.Push()],
        [sg.Push(), sg.Button("OK", key="Exit", enable_events=True), sg.Push()],
        [sg.VPush()]
    ]
    window = sg.Window("Success", layout, finalize=True, icon="src/icon.ico")
    window.set_min_size((300, 1))
    while True:
        event, values = window.read()
        if event == sg.WIN_CLOSED:
            break
        if event == "Exit":
            window.close()
            break


def show_info(msg):
    layout = [
        [sg.VPush()],
        [sg.Push(), sg.Text(msg, justification="center"),
         sg.Push()],
        [sg.Push(), sg.Button("OK", key="Exit", enable_events=True), sg.Push()],
        [sg.VPush()]
    ]
    window = sg.Window("Info", layout, finalize=True, icon="src/icon.ico")
    window.set_min_size((300, 1))
    while True:
        event, values = window.read()
        if event == sg.WIN_CLOSED:
            break
        if event == "Exit":
            window.close()
            break


def show_warning(msg):
    layout = [
        [sg.VPush()],
        [sg.Push(), sg.Text(msg, justification="center"),
         sg.Push()],
        [sg.Push(), sg.Button("OK", key="Exit", enable_events=True), sg.Push()],
        [sg.VPush()]
    ]
    window = sg.Window("Warning", layout, finalize=True, icon="src/icon.ico")
    window.set_min_size((300, 1))
    while True:
        event, values = window.read()
        if event == sg.WIN_CLOSED:
            break
        if event == "Exit":
            window.close()
            break


def show_custom_prompt(msg, title, button):
    layout = [
        [sg.VPush()],
        [sg.Push(), sg.Text(msg, justification="center"),
         sg.Push()],
        [sg.Push(), sg.Button(button, key="Exit", enable_events=True), sg.Push()],
        [sg.VPush()]
    ]
    window = sg.Window(title, layout, finalize=True, icon="src/icon.ico")
    window.set_min_size((300, 1))

    while True:
        event, values = window.read()
        if event == sg.WIN_CLOSED:
            return False
        if event == "Exit":
            window.close()
            return True
