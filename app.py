import os
import re
import subprocess
import sys
from enum import Enum

import objc
import rumps
from AppKit import (
    NSWindowStyleMaskTitled,
    NSWindowStyleMaskClosable,
    NSBackingStoreBuffered,
    NSFloatingWindowLevel
)
from Cocoa import (
    NSPanel, NSTextField, NSMakeRect,
    NSButton, NSApplication, NSDistributedNotificationCenter,
    NSImageView, NSImage, NSFont, NSAttributedString, NSHTMLTextDocumentType,
    NSFontAttributeName, NSMutableParagraphStyle, NSParagraphStyleAttributeName, NSTextAlignmentCenter,
    NSForegroundColorAttributeName, NSColor, NSOnState, NSOffState,
    NSSegmentedControl, NSSegmentSwitchTrackingSelectOne, NSRegularControlSize, NSImageScaleProportionallyDown,
    NSSwitchButton, NSPopUpButton, NSComboBox, NSMenu, NSMenuItem
)
from Foundation import NSBundle, NSData, NSDictionary

from version import VERSION


class FieldType(Enum):
    TEXT = "text"
    COMBOBOX = "combobox"


class Appearance(Enum):
    LIGHT = "LIGHT"
    DARK = "DARK"


class ProcessState(Enum):
    INITIAL = "INITIAL"
    RUNNING = "RUNNING"
    STOPPED_PARTIALLY = "STOPPED_PARTIALLY"
    STOPPED = "STOPPED"
    ERROR = "ERROR"


class LogoStyle(Enum):
    GEAR = "GEAR"
    COLORED_GLASSES = "COLORED_GLASSES"
    COLORED_S = "COLORED_S"


DEFAULT_LOGO_STYLE = LogoStyle.COLORED_GLASSES


def get_appearance() -> Appearance:
    app = NSApplication.sharedApplication()
    appearance = app.effectiveAppearance().name()
    return Appearance.DARK if Appearance.DARK.value.lower() in appearance.lower() else Appearance.LIGHT


def get_logo_style_image(style: LogoStyle, state: ProcessState = ProcessState.STOPPED_PARTIALLY,
                         appearance: Appearance = None) -> str:
    appearance = appearance or get_appearance()
    appearance = Appearance.LIGHT if appearance == Appearance.DARK else Appearance.DARK
    return os.path.join("images", "icons", style.value.lower(), appearance.value.lower(), f"{state.value.lower()}.svg")


def alert_foreground(title, message, ok=None, cancel=None, other=None, icon_path=None) -> int:
    NSApplication.sharedApplication().activateIgnoringOtherApps_(True)
    return rumps.alert(title, message, ok, cancel, other, icon_path)


def bring_app_to_front(self: NSPanel):
    NSApplication.sharedApplication().activateIgnoringOtherApps_(True)
    self.center()
    self.makeKeyAndOrderFront_(None)


def resource_path(rel_path):
    # on macOS bundle, resources are in Contents/Resources
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        base = sys._MEIPASS
    else:
        # running normally: project root
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, rel_path)


class FormValidator:
    @staticmethod
    # def validate_ip(ip: str) -> bool:
    #     parts = ip.split('.')
    #     if len(parts) != 4:
    #         return False
    #     for part in parts:
    #         if not part.isdigit() or not (0 <= int(part) <= 255):
    #             return False
    #     return True

    @staticmethod
    def validate_port(port) -> bool:
        return port.isdigit() and 1 <= int(port) <= 65535

    @staticmethod
    def validate_port_with_alert(port, label: str):
        if not FormValidator.validate_port(port):
            alert_foreground("Error", f"{label} must be a valid port between 1 and 65535")
            return False
        return True

    @staticmethod
    def validate_empty_with_alert(value, label):
        if not value:
            alert_foreground("Error", f"{label} must not be empty")
            return False
        return True


class ConfigHelper:
    yq_path = resource_path(os.path.join('bin', 'yq'))
    workspace_path = os.path.expanduser("~/.susops")
    config_path = os.path.join(workspace_path, "config.yaml")

    @staticmethod
    def get_connection_tags():
        result = ConfigHelper.read_config(".connections[].tag", [])
        return result.splitlines()

    @staticmethod
    def get_domains():
        result = ConfigHelper.read_config(".connections[].pac_hosts[]", [])
        split_result = result.splitlines()
        return split_result

    @staticmethod
    def get_local_forwards():
        result = ConfigHelper.read_config(".connections[].forwards.local[] | \"\\(.tag) (\\(.src) → \\(.dst))\"", [])
        # filter result items, remove all items equal to "( → )" (this is the case when no remote forwards are set)
        result = [item for item in result.splitlines() if not item == "( → )"]
        return result

    @staticmethod
    def get_remote_forwards():
        result = ConfigHelper.read_config(".connections[].forwards.remote[] | \"\\(.tag) (\\(.src) → \\(.dst))\"", [])
        # filter result items, remove all items equal to "( → )" (this is the case when no remote forwards are set)
        result = [item for item in result.splitlines() if not item == "( → )"]
        return result

    @staticmethod
    def read_config(query: str, default):
        try:
            result = subprocess.check_output([ConfigHelper.yq_path, "e", query, ConfigHelper.config_path], encoding="utf-8").strip()
            if result == "null":
                result = default
        except subprocess.CalledProcessError:
            result = default
        return result

    @staticmethod
    def update_config(query: str):
        subprocess.run([ConfigHelper.yq_path, "e", "-i", query, ConfigHelper.config_path, ], check=True)


def add_bin_to_path():
    os.environ['PATH'] = resource_path('bin') + os.pathsep + os.environ.get('PATH', '')


from pathlib import Path
from typing import List

def get_ssh_hosts(config_path: Path = None) -> List[str]:
    if config_path is None:
        config_path = Path(os.path.expanduser("~/.ssh/config"))

    host_pattern = re.compile(r'^\s*Host\s+(.*)$', re.IGNORECASE)
    hosts = []

    try:
        with config_path.open('r') as f:
            for raw in f:
                line = raw.strip()
                # skip blanks and comments
                if not line or line.startswith('#'):
                    continue
                m = host_pattern.match(line)
                if m:
                    # a Host line can list multiple names/patterns
                    for h in m.group(1).split():
                        hosts.append(h)
    except FileNotFoundError:
        raise FileNotFoundError(f"SSH config not found: {config_path!s}")

    return hosts


def run_susops(command, show_alert=True):
    susops_path = resource_path(os.path.join('bin', 'susops'))
    result = subprocess.run(f"{susops_path} {command}", shell=True, capture_output=True, encoding="utf-8",
                            errors="ignore")
    if result.returncode != 0 and show_alert:
        alert_foreground("Error", result.stdout.strip())
    return result.stdout.strip(), result.returncode


# Global instance of the app
susops_app = None  # type: SusOpsApp|None


def add_edit_menu_item():
    app = NSApplication.sharedApplication()
    main_menu = app.mainMenu()

    if main_menu is None:
        main_menu = NSMenu.alloc().init()
        app.setMainMenu_(main_menu)

    # only initialize once
    if main_menu.itemWithTitle_("Edit") is not None:
        return

    edit_menu = NSMenu.alloc().initWithTitle_("Edit")
    edit_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_("Edit", None, "")
    edit_item.setSubmenu_(edit_menu)

    edit_menu.addItem_(NSMenuItem.alloc().initWithTitle_action_keyEquivalent_("Undo", "undo:", "z"))
    edit_menu.addItem_(NSMenuItem.alloc().initWithTitle_action_keyEquivalent_("Redo", "redo:", "Z"))
    edit_menu.addItem_(NSMenuItem.separatorItem())
    edit_menu.addItem_(NSMenuItem.alloc().initWithTitle_action_keyEquivalent_("Cut", "cut:", "x"))
    edit_menu.addItem_(NSMenuItem.alloc().initWithTitle_action_keyEquivalent_("Copy", "copy:", "c"))
    edit_menu.addItem_(NSMenuItem.alloc().initWithTitle_action_keyEquivalent_("Paste", "paste:", "v"))
    edit_menu.addItem_(NSMenuItem.separatorItem())
    edit_menu.addItem_(NSMenuItem.alloc().initWithTitle_action_keyEquivalent_("Select All", "selectAll:", "a"))

    main_menu.addItem_(edit_item)

class SusOpsApp(rumps.App):
    def __init__(self, icon_dir=None):
        global susops_app
        susops_app = self
        add_bin_to_path()

        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.images_dir = icon_dir or os.path.join(self.base_dir, 'images')
        self.process_state = ProcessState.INITIAL

        super(SusOpsApp, self).__init__(name="SO", icon=None, quit_button=None)

        # Observe theme changes
        center = NSDistributedNotificationCenter.defaultCenter()
        selector = objc.selector(
            self.appearanceChanged_,
            selector=b'appearanceChanged:',
            signature=b'v@:@'
        )
        center.addObserver_selector_name_object_(
            self,
            selector,
            'AppleInterfaceThemeChangedNotification',
            None
        )

        # Set initial icon based on current appearance
        self.config = self.load_config()
        self.update_icon()

        self._settings_panel = None
        self._connection_panel = None
        self._remove_connection_panel = None
        self._add_host_panel = None
        self._remove_host_panel = None
        self._add_local_forward_panel = None
        self._remove_local_forward_panel = None
        self._add_remote_forward_panel = None
        self._remove_remote_forward_panel = None
        self._about_panel = None

        self.menu = [
            rumps.MenuItem("Status", callback=self.check_status),
            None,
            rumps.MenuItem("Settings…", callback=self.open_settings, key=","),
            None,
            (rumps.MenuItem("Add"), [
                rumps.MenuItem("Add Connection", callback=self.add_connection),
                rumps.MenuItem("Add Domain", callback=self.add_domain),
                rumps.MenuItem("Add Local Forward", callback=self.add_local_forward),
                rumps.MenuItem("Add Remote Forward", callback=self.add_remote_forward),
            ]),
            (rumps.MenuItem("Remove"), [
                rumps.MenuItem("Remove Connection", callback=self.remove_connection),
                rumps.MenuItem("Remove Domain", callback=self.remove_domain),
                rumps.MenuItem("Remove Local Forward", callback=self.remove_local_forward),
                rumps.MenuItem("Remove Remote Forward", callback=self.remove_remote_forward),
            ]),
            rumps.MenuItem("List All", callback=self.list_config),
            rumps.MenuItem("Open Config File", callback=self.open_config_file),
            None,
            rumps.MenuItem("Start Proxy", callback=self.start_proxy),
            rumps.MenuItem("Stop Proxy", callback=self.stop_proxy),
            rumps.MenuItem("Restart Proxy", callback=self.restart_proxy, key="r"),
            None,
            ("Test", [
                rumps.MenuItem("Test Any", callback=self.test_any),
                rumps.MenuItem("Test All", callback=self.test_all),
            ]),
            ("Launch Browser", [
                ("Chrome", [
                    rumps.MenuItem("Launch Chrome", callback=self.launch_chrome),
                    rumps.MenuItem("Open Chrome Proxy Settings", callback=self.launch_chrome_proxy_settings),
                ]),
                ("Firefox", [
                    rumps.MenuItem("Launch Firefox", callback=self.launch_firefox),
                ]),
            ]),
            None,
            rumps.MenuItem("Reset All", callback=self.reset),
            None,
            rumps.MenuItem("About SusOps", callback=self.open_about),
            rumps.MenuItem("Quit", callback=self.quit_app, key="q")
        ]

        self._check_timer = rumps.Timer(self.check_state_and_update_menu, 5)

        self._startup_check_timer = rumps.Timer(self.async_startup_check, 0.1)
        self._startup_check_timer.start()

    def async_startup_check(self, _):
        add_edit_menu_item()
        status, output, returncode = self.check_state_and_update_menu()
        # check if output has "no default connection found"
        if status == ProcessState.ERROR and "no default connection found" in output:
            # show welcome dialog for connection setup
            alert_foreground("🎉 Welcome to SusOps 🎉",
                             "To get started, please follow these steps:\n\n"
                             "1. Add a connection\n"
                             "2. Start the proxy\n\n"
                             "If you need help, please check the documentation in 'About' → 'Github'.", )
        self._startup_check_timer.stop()
        self._check_timer.start()

    def check_state_and_update_menu(self, _=None):
        # runs every 5s
        try:
            output, returncode = run_susops("ps", False)
        except subprocess.CalledProcessError:
            output, returncode = "Error running command", -1

        if not output:
            returncode = -1

        match returncode:
            case 0:
                new_state = ProcessState.RUNNING
            case 2:
                new_state = ProcessState.STOPPED_PARTIALLY
            case 3:
                new_state = ProcessState.STOPPED
            case _:
                new_state = ProcessState.ERROR

        if new_state == self.process_state:
            return

        self.process_state = new_state
        self.update_icon()

        self.menu["Status"].title = f"Status: {self.process_state.value.lower().replace("_", " ")}"
        self.menu["Status"].icon = os.path.join(self.images_dir, "status", self.process_state.value.lower() + ".svg")

        match self.process_state:
            case ProcessState.RUNNING:
                self.menu["Start Proxy"].set_callback(None)
                self.menu["Stop Proxy"].set_callback(self.stop_proxy)
                self.menu["Restart Proxy"].set_callback(self.restart_proxy)
                self.menu["Test"]["Test Any"].set_callback(self.test_any)
                self.menu["Test"]["Test All"].set_callback(self.test_all)
            case ProcessState.STOPPED_PARTIALLY:
                self.menu["Start Proxy"].set_callback(self.start_proxy)
                self.menu["Stop Proxy"].set_callback(self.stop_proxy)
                self.menu["Restart Proxy"].set_callback(self.restart_proxy)
                self.menu["Test"]["Test Any"].set_callback(self.test_any)
                self.menu["Test"]["Test All"].set_callback(self.test_all)
            case ProcessState.STOPPED:
                self.menu["Start Proxy"].set_callback(self.start_proxy)
                self.menu["Stop Proxy"].set_callback(None)
                self.menu["Restart Proxy"].set_callback(None)
                self.menu["Test"]["Test Any"].set_callback(None)
                self.menu["Test"]["Test All"].set_callback(None)
            case ProcessState.ERROR:
                self.menu["Start Proxy"].set_callback(None)
                self.menu["Stop Proxy"].set_callback(None)
                self.menu["Restart Proxy"].set_callback(None)
                self.menu["Test"]["Test Any"].set_callback(None)
                self.menu["Test"]["Test All"].set_callback(None)

        return self.process_state, output, returncode

    def appearanceChanged_(self, _):
        # Called when user switches between light/dark mode
        self.update_icon()
        if self._settings_panel:
            self._settings_panel.update_appearance()

    def update_icon(self, logo_style: LogoStyle = None):
        logo_style = logo_style or LogoStyle[self.config['logo_style'].upper()]
        state = ProcessState.STOPPED if self.process_state == ProcessState.INITIAL else self.process_state
        self.icon = get_logo_style_image(logo_style, state)

    @staticmethod
    def load_config():
        configs = {
            "pac_server_port": ConfigHelper.read_config(".pac_server_port", "1081"),
            "logo_style": ConfigHelper.read_config(".susops_app.logo_style", DEFAULT_LOGO_STYLE.value),
            "stop_on_quit": ConfigHelper.read_config(".susops_app.stop_on_quit", '1') == '1',
            "ephemeral_ports": ConfigHelper.read_config(".susops_app.ephemeral_ports", '1') == '1'
        }

        # check if logo_style is valid
        if configs['logo_style'] not in LogoStyle.__members__:
            configs['logo_style'] = DEFAULT_LOGO_STYLE.value
            ConfigHelper.update_config(f".susops_app.logo_style = \"{configs['logo_style']}\"")
        return configs

    def open_settings(self, _):
        if self._settings_panel is None:
            frame = NSMakeRect(0, 0, 300, 240)
            style = (NSWindowStyleMaskTitled | NSWindowStyleMaskClosable)
            self._settings_panel = SettingsPanel.alloc().initWithContentRect_styleMask_backing_defer_(
                frame, style, NSBackingStoreBuffered, False
            )
        self.config = self.load_config()
        self._settings_panel.pac_port_field.setStringValue_(self.config['pac_server_port'])

        app_path = os.path.basename(NSBundle.mainBundle().bundlePath())
        app_name = os.path.splitext(os.path.basename(app_path))[0]
        script = 'tell application "System Events" to get name of every login item'
        try:
            out = subprocess.check_output(["osascript", "-e", script])
            launch_at_login = app_name in out.decode()
        except:
            launch_at_login = False
        self._settings_panel.launch_at_login_checkbox.setState_(NSOnState if launch_at_login else NSOffState)

        self._settings_panel.stop_on_quit_checkbox.setState_(NSOnState if self.config['stop_on_quit'] else NSOffState)
        self._settings_panel.ephemeral_ports_checkbox.setState_(NSOnState if self.config['ephemeral_ports'] else NSOffState)

        # get index of current logo style
        logo_style = self.config['logo_style']
        selected_index = list(LogoStyle).index(LogoStyle[logo_style.upper()])
        self._settings_panel.segmented_icons.setSelectedSegment_(selected_index)
        self._settings_panel.run()

    def show_restart_dialog(self, title, message):
        if self.process_state != ProcessState.RUNNING:
            alert_foreground(title, message)
            return

        restart = alert_foreground(
            title,
            message,
            ok="Restart Proxy", cancel="Skip"
        )

        if restart == 1:
            self.restart_proxy(None)

    def add_connection(self, sender, default_text=''):
        frame_width = 440
        frame_height = 195
        if not self._connection_panel:
            frame = NSMakeRect(0, 0, frame_width, frame_height)
            style = (NSWindowStyleMaskTitled | NSWindowStyleMaskClosable)
            self._connection_panel = AddConnectionPanel.alloc().initWithContentRect_styleMask_backing_defer_(
                frame, style, NSBackingStoreBuffered, False
            )
            self._connection_panel.setTitle_("Add Connection")
            self._connection_panel.configure_fields([
                ('tag', "Connection Tag:", FieldType.TEXT),
                ('host', "SSH Host:", FieldType.COMBOBOX),
                ('socks_proxy_port', "SOCKS Proxy Port (optional):", FieldType.TEXT),
            ], label_width=170, input_start_x=190, input_width=230, hide_connection=True)
        self._connection_panel.run()

    def add_domain(self, sender, default_text=''):
        frame_width = 280
        frame_height = 195
        if not self._add_host_panel:
            frame = NSMakeRect(0, 0, frame_width, frame_height)
            style = (NSWindowStyleMaskTitled | NSWindowStyleMaskClosable)
            self._add_host_panel = AddHostPanel.alloc().initWithContentRect_styleMask_backing_defer_(
                frame, style, NSBackingStoreBuffered, False
            )
            self._add_host_panel.setTitle_("Add Domain")
            self._add_host_panel.configure_fields([
                ('host', "Domain:", FieldType.TEXT),
            ], label_width=80, input_start_x=100)
            self._add_host_panel.add_info_label("This domain and one level of subdomains \nwill be added to the PAC rules.", frame_width, frame_height)
        self._add_host_panel.run()

    def add_local_forward(self, _):
        if not self._add_local_forward_panel:
            frame = NSMakeRect(0, 0, 320, 230)
            style = (NSWindowStyleMaskTitled | NSWindowStyleMaskClosable)
            self._add_local_forward_panel = LocalForwardPanel.alloc().initWithContentRect_styleMask_backing_defer_(
                frame, style, NSBackingStoreBuffered, False
            )
            self._add_local_forward_panel.setTitle_("Add Local Forward")
            self._add_local_forward_panel.configure_fields([
                ('tag', 'Tag (optional):', FieldType.TEXT),
                ('local_port_field', 'Forward Local Port:', FieldType.TEXT),
                ('remote_port_field', 'To Remote Port:', FieldType.TEXT),
            ], label_width=120, input_start_x=140)
        self._add_local_forward_panel.run()

    def add_remote_forward(self, _):
        if not self._add_remote_forward_panel:
            frame = NSMakeRect(0, 0, 330, 230)
            style = (NSWindowStyleMaskTitled | NSWindowStyleMaskClosable)
            self._add_remote_forward_panel = RemoteForwardPanel.alloc().initWithContentRect_styleMask_backing_defer_(
                frame, style, NSBackingStoreBuffered, False
            )
            self._add_remote_forward_panel.setTitle_("Add Remote Forward")
            self._add_remote_forward_panel.configure_fields([
                ('tag', 'Tag (optional):', FieldType.TEXT),
                ('remote_port_field', 'Forward Remote Port:', FieldType.TEXT),
                ('local_port_field', 'To Local Port:', FieldType.TEXT),
            ], label_width=130, input_start_x=150)
        self._add_remote_forward_panel.run()

    def remove_connection(self, _):
        if not self._remove_connection_panel:
            frame = NSMakeRect(0, 0, 300, 105)
            style = (NSWindowStyleMaskTitled | NSWindowStyleMaskClosable)
            self._remove_connection_panel = RemoveConnectionPanel.alloc().initWithContentRect_styleMask_backing_defer_(
                frame, style, NSBackingStoreBuffered, False
            )
            self._remove_connection_panel.setTitle_("Remove Connection")
            self._remove_connection_panel.configure_field("Connection Tag:", label_width = 100, input_start_x = 120)
        self._remove_connection_panel.update_items(ConfigHelper.get_connection_tags())
        self._remove_connection_panel.run()

    def remove_domain(self, _):
        if not self._remove_host_panel:
            frame = NSMakeRect(0, 0, 255, 105)
            style = (NSWindowStyleMaskTitled | NSWindowStyleMaskClosable)
            self._remove_host_panel = RemoveDomainPanel.alloc().initWithContentRect_styleMask_backing_defer_(
                frame, style, NSBackingStoreBuffered, False
            )
            self._remove_host_panel.setTitle_("Remove Domain")
            self._remove_host_panel.configure_field("Domain:", label_width = 55, input_start_x = 75)
        self._remove_host_panel.update_items(ConfigHelper.get_domains())
        self._remove_host_panel.run()

    def remove_local_forward(self, sender, default_text=''):
        if not self._remove_local_forward_panel:
            frame = NSMakeRect(0, 0, 290, 105)
            style = (NSWindowStyleMaskTitled | NSWindowStyleMaskClosable)
            self._remove_local_forward_panel = RemoveLocalForwardPanel.alloc().initWithContentRect_styleMask_backing_defer_(
                frame, style, NSBackingStoreBuffered, False
            )
            self._remove_local_forward_panel.setTitle_("Remove Local Forward")
            self._remove_local_forward_panel.configure_field("Local Forward:", label_width=90, input_start_x=110)
        self._remove_local_forward_panel.update_items(ConfigHelper.get_local_forwards())
        self._remove_local_forward_panel.run()

    def remove_remote_forward(self, sender, default_text=''):
        if not self._remove_remote_forward_panel:
            frame = NSMakeRect(0, 0, 310, 105)
            style = (NSWindowStyleMaskTitled | NSWindowStyleMaskClosable)
            self._remove_remote_forward_panel = RemoveRemoteForwardPanel.alloc().initWithContentRect_styleMask_backing_defer_(
                frame, style, NSBackingStoreBuffered, False
            )
            self._remove_remote_forward_panel.setTitle_("Remove Remote Forward")
            self._remove_remote_forward_panel.configure_field("Remote Forward:", label_width=110, input_start_x=130)
        self._remove_remote_forward_panel.update_items(ConfigHelper.get_remote_forwards())
        self._remove_remote_forward_panel.run()

    def list_config(self, _):
        output, _ = run_susops("ls")
        alert_foreground("Domains & Forwards", output)

    def open_config_file(self, _):
        run_susops("config")

    def start_proxy(self, _):
        output, _ = run_susops("start")
        self.check_state_and_update_menu()

    def stop_proxy(self, _):
        ports_flag = "--keep-ports" if not self.config['ephemeral_ports'] else ""

        output, _ = run_susops(f"stop {ports_flag}")
        self.check_state_and_update_menu()

    def restart_proxy(self, _):
        self.config = self.load_config()
        output, _ = run_susops("restart")
        self.check_state_and_update_menu()

    def check_status(self, _):
        output, _ = run_susops("ps", False)
        alert_foreground("SusOps Status", output)

    def test_any(self, _):
        host = rumps.Window("Enter domain or port to test: ", "Test Any",
                            ok="Test", cancel="Cancel", dimensions=(220, 20)).run().text
        if host:
            output, _ = run_susops(f"test {host}", False)
            alert_foreground("SusOps Test", output)

    def test_all(self, _):
        output, _ = run_susops("test --all", False)
        alert_foreground("SusOps Test All", output)

    def launch_chrome(self, _):
        output, _ = run_susops("chrome", False)

    def launch_chrome_proxy_settings(self, _):
        output, _ = run_susops("chrome-proxy-settings", False)

    def launch_firefox(self, _):
        output, _ = run_susops("firefox", False)

    def reset(self, _):
        result = alert_foreground(
            "Reset Everything?",
            "This will stop SusOps and remove all of its configs. You will have to reconfigure the ssh host as well as ports.\n\nAre you sure?",
            ok="Reset Everything", cancel="Cancel"
        )

        if result == 1:
            run_susops("reset --force", False)
            self.config = self.load_config()
            self.update_icon()

    def open_about(self, _):
        if self._about_panel is None:
            frame = NSMakeRect(0, 0, 280, 190)
            style = (NSWindowStyleMaskTitled | NSWindowStyleMaskClosable)
            self._about_panel = AboutPanel.alloc().initWithContentRect_styleMask_backing_defer_(
                frame, style, NSBackingStoreBuffered, False
            )
        self._about_panel.run()

    def quit_app(self, _):
        if self.config['stop_on_quit']:
            run_susops("stop --keep-ports", False)
        rumps.quit_application()


class SettingsPanel(NSPanel):
    """A floating panel with SSH Host, SOCKS Port & PAC Port fields plus Save/Cancel."""

    def initWithContentRect_styleMask_backing_defer_(
            self, frame, style, backing, defer
    ):
        self = objc.super(SettingsPanel, self).initWithContentRect_styleMask_backing_defer_(
            frame, style, backing, defer
        )
        if not self:
            return None

        self.setHidesOnDeactivate_(False)

        self.setTitle_("Settings")
        self.setLevel_(NSFloatingWindowLevel)
        content = self.contentView()
        win_h = frame.size.height
        label_margin_left = 20
        label_width = 70
        input_margin_left = 100
        input_width = 180
        element_height = 24

        # --- Launch at Login Checkbox ---
        y = win_h - 40
        self.launch_at_login_checkbox = NSButton.alloc().initWithFrame_(NSMakeRect(input_margin_left, y, input_width, element_height))
        self.launch_at_login_checkbox.setButtonType_(NSSwitchButton)
        self.launch_at_login_checkbox.setTitle_("Launch at Login")

        self.launch_at_login_checkbox.setTarget_(self)
        # self.launch_at_login_checkbox.setAction_("toggleLaunchAtLogin:")
        content.addSubview_(self.launch_at_login_checkbox)

        # --- Stop On Close Checkbox ---
        y -= 30
        self.stop_on_quit_checkbox = NSButton.alloc().initWithFrame_(NSMakeRect(input_margin_left, y, input_width, element_height))
        self.stop_on_quit_checkbox.setButtonType_(NSSwitchButton)
        self.stop_on_quit_checkbox.setTitle_("Stop Proxy On Quit")

        self.stop_on_quit_checkbox.setTarget_(self)
        content.addSubview_(self.stop_on_quit_checkbox)

        # --- Ephemeral Ports Checkbox ---
        y -= 30
        self.ephemeral_ports_checkbox = NSButton.alloc().initWithFrame_(NSMakeRect(input_margin_left, y, input_width, element_height))
        self.ephemeral_ports_checkbox.setButtonType_(NSSwitchButton)
        self.ephemeral_ports_checkbox.setTitle_("Random SSH Ports On Start")

        self.ephemeral_ports_checkbox.setTarget_(self)
        content.addSubview_(self.ephemeral_ports_checkbox)

        # --- Logo Style ---
        y -= 40
        self.logo_label = NSTextField.alloc().initWithFrame_(NSMakeRect(label_margin_left, y - 4, label_width, element_height))
        self.logo_label.setStringValue_("Logo Style:")
        self.logo_label.setAlignment_(2)
        self.logo_label.setBezeled_(False)
        self.logo_label.setDrawsBackground_(False)
        self.logo_label.setEditable_(False)
        content.addSubview_(self.logo_label)

        self.segmented_icons = NSSegmentedControl.alloc().initWithFrame_(NSMakeRect(input_margin_left, y, input_width, element_height))
        self.segmented_icons.setSegmentCount_(len(LogoStyle))
        self.segmented_icons.setTrackingMode_(NSSegmentSwitchTrackingSelectOne)
        self.segmented_icons.setControlSize_(NSRegularControlSize)

        self.update_appearance()

        self.segmented_icons.setTarget_(self)
        self.segmented_icons.setAction_("segmentedIconsChange:")  # define this method to handle clicks
        content.addSubview_(self.segmented_icons)

        # --- PAC Port ---
        y -= 40
        self.pac_label = NSTextField.alloc().initWithFrame_(NSMakeRect(label_margin_left, y - 4, label_width, element_height))
        self.pac_label.setStringValue_("PAC Port:")
        self.pac_label.setAlignment_(2)
        self.pac_label.setBezeled_(False)
        self.pac_label.setDrawsBackground_(False)
        self.pac_label.setEditable_(False)
        content.addSubview_(self.pac_label)

        self.pac_port_field = NSTextField.alloc().initWithFrame_(NSMakeRect(input_margin_left, y, input_width, element_height))
        content.addSubview_(self.pac_port_field)

        # --- Save/Cancel Buttons ---
        button_x = input_margin_left - 5
        button_width = 90
        button_margin = 10

        y -= 40
        cancel_btn = NSButton.alloc().initWithFrame_(NSMakeRect(button_x, y, button_width, element_height))
        cancel_btn.setTitle_("Cancel")
        cancel_btn.setBezelStyle_(1)
        cancel_btn.setTarget_(self)
        cancel_btn.setAction_("cancelSettings:")
        content.addSubview_(cancel_btn)

        save_btn = NSButton.alloc().initWithFrame_(NSMakeRect(button_x + button_width + button_margin, y, button_width, element_height))
        save_btn.setTitle_("Save")
        save_btn.setBezelStyle_(1)
        save_btn.setKeyEquivalent_("\r")
        save_btn.setTarget_(self)
        save_btn.setAction_("saveSettings:")
        content.addSubview_(save_btn)

        return self

    def update_appearance(self):
        # add / update logo segmented control
        for idx, style in enumerate(LogoStyle):
            icon = NSImage.alloc().initWithContentsOfFile_(get_logo_style_image(style))
            icon.setSize_((24, 24))
            self.segmented_icons.setImage_forSegment_(icon, idx)
            self.segmented_icons.cell().setImageScaling_forSegment_(NSImageScaleProportionallyDown, idx)

    def saveSettings_(self, _):
        self.toggleLaunchAtLogin_(self.launch_at_login_checkbox)

        ws = os.path.expanduser("~/.susops")
        os.makedirs(ws, exist_ok=True)

        pac_server_port = self.pac_port_field.stringValue().strip()
        if not FormValidator.validate_port_with_alert(pac_server_port, self.pac_label.stringValue().rstrip(':')):
            return
        ConfigHelper.update_config(f".pac_server_port = {pac_server_port}")

        stop_on_quit = self.stop_on_quit_checkbox.stringValue().strip()
        if not FormValidator.validate_empty_with_alert(stop_on_quit, self.stop_on_quit_checkbox.stringValue().rstrip(':')):
            return
        ConfigHelper.update_config(f".susops_app.stop_on_quit = \"{stop_on_quit}\"")

        ephemeral_ports = self.ephemeral_ports_checkbox.stringValue().strip()
        if not FormValidator.validate_empty_with_alert(ephemeral_ports, self.ephemeral_ports_checkbox.stringValue().rstrip(':')):
            return
        ConfigHelper.update_config(f".susops_app.ephemeral_ports = \"{ephemeral_ports}\"")

        selected_index = self.segmented_icons.selectedSegment()
        selected_style = list(LogoStyle)[selected_index]
        ConfigHelper.update_config(f".susops_app.logo_style = \"{selected_style.value}\"")

        susops_app.config = susops_app.load_config()
        susops_app.update_icon()

        self.close()
        susops_app.show_restart_dialog("Settings Saved", "Settings will be applied on next proxy start.")

    def segmentedIconsChange_(self, sender):
        selected_index = sender.selectedSegment()
        selected_style = list(LogoStyle)[selected_index]

        # temporarily set the icon to the selected style
        susops_app.config['logo_style'] = selected_style.value
        susops_app.update_icon(selected_style)

    def toggleLaunchAtLogin_(self, sender):
        enabled = (sender.state() == NSOnState)
        bundle = NSBundle.mainBundle()
        app_path = bundle.bundlePath()
        bin_name = os.path.splitext(os.path.basename(app_path))[0]

        if enabled:
            applescript = '''
                tell application "System Events"
                    make login item at end with properties {path:"%s", hidden:false}
                end tell
            ''' % app_path
        else:
            applescript = '''
                tell application "System Events"
                    delete login item "%s"
                end tell
            ''' % bin_name

        subprocess.call(["osascript", "-e", applescript])

    def cancelSettings_(self, _):
        # reset the logo style to the saved one
        susops_app.config = susops_app.load_config()
        susops_app.update_icon()
        self.close()

    def run(self):
        bring_app_to_front(self)


class GenericFieldPanel(NSPanel):

    def initWithContentRect_styleMask_backing_defer_(
            self, frame, style, backing, defer
    ):
        self = objc.super(GenericFieldPanel, self).initWithContentRect_styleMask_backing_defer_(
            frame, style, backing, defer
        )
        if not self:
            return None

        self.setHidesOnDeactivate_(False)
        self.setLevel_(NSFloatingWindowLevel)

        return self

    def configure_fields(self, field_defs, label_width: int = 150, input_start_x: int = 170, input_width: int = 160,
                         hide_connection: bool = False):
        """
        field_defs = [(attr_name, label_text), ...]   # order = top → bottom
        Builds one label/field row per entry, 40 px vertical spacing.
        """

        content = self.contentView()

        y = 20 + 40 + len(field_defs) * 40

        if not hide_connection:
            # select for connections with NSPopUpButton
            lbl = NSTextField.alloc().initWithFrame_(NSMakeRect(15, y - 2, label_width, 24))
            lbl.setStringValue_("Connection:")
            lbl.setAlignment_(2)
            lbl.setBezeled_(False)
            lbl.setDrawsBackground_(False)
            lbl.setEditable_(False)
            content.addSubview_(lbl)

            self.connection = NSPopUpButton.alloc().initWithFrame_(NSMakeRect(input_start_x, y, input_width, 24))
            self.connection.setPullsDown_(False)
            self.connection.addItemsWithTitles_(ConfigHelper.get_connection_tags())
            self.connection.selectItemAtIndex_(0)
            content.addSubview_(self.connection)
        y -= 40

        for attr, label, type in field_defs:
            lbl = NSTextField.alloc().initWithFrame_(NSMakeRect(15, y - 2, label_width, 24))
            lbl.setStringValue_(label)
            lbl.setAlignment_(2)
            lbl.setBezeled_(False)
            lbl.setDrawsBackground_(False)
            lbl.setEditable_(False)
            content.addSubview_(lbl)
            if type == FieldType.COMBOBOX:
                fld = NSComboBox.alloc().initWithFrame_(NSMakeRect(input_start_x, y, input_width + 3, 24))
                fld.addItemsWithObjectValues_(ConfigHelper.get_connection_tags())
            else:
                fld = NSTextField.alloc().initWithFrame_(NSMakeRect(input_start_x, y, input_width, 24))
            content.addSubview_(fld)
            setattr(self, attr, fld)
            y -= 40

        # --- Save/Cancel Buttons ---
        button_width = 80
        button_spacing = 7
        cancel_btn = NSButton.alloc().initWithFrame_(NSMakeRect(input_start_x - 5, 16, button_width, 30))
        cancel_btn.setTitle_("Cancel")
        cancel_btn.setBezelStyle_(1)
        cancel_btn.setTarget_(self)
        cancel_btn.setAction_("cancel:")
        content.addSubview_(cancel_btn)

        add_btn = NSButton.alloc().initWithFrame_(NSMakeRect(input_start_x + input_width - button_width + button_spacing, 16, button_width, 30))
        add_btn.setTitle_("Add")
        add_btn.setBezelStyle_(1)
        add_btn.setKeyEquivalent_("\r")
        add_btn.setTarget_(self)
        add_btn.setAction_("add:")
        content.addSubview_(add_btn)

    def run(self):
        bring_app_to_front(self)
        # reload connection tags
        if hasattr(self, 'connection'):
            self.connection.removeAllItems()
            self.connection.addItemsWithTitles_(ConfigHelper.get_connection_tags())

    def cancel_(self, _):
        self.close()


class GenericSelectPanel(NSPanel):
    """A simple panel with a label, a dropdown, and Save/Cancel buttons."""

    def initWithContentRect_styleMask_backing_defer_(
            self, frame, style, backing, defer
    ):
        self = objc.super(GenericSelectPanel, self).initWithContentRect_styleMask_backing_defer_(
            frame, style, backing, defer
        )
        if not self:
            return None

        self.setHidesOnDeactivate_(False)
        self.setLevel_(NSFloatingWindowLevel)

        return self

    def configure_field(self, label_text: str, label_width: int = 100, input_start_x: int = 120, input_width: int = 150, save_button_text: str = "Remove"):
        """
        Configures the panel with a single label and NSPopUpButton.
        :param label_text: The text for the label.
        :param label_width: Width of the label.
        :param input_start_x: X-coordinate for the NSPopUpButton.
        :param input_width: Width of the NSPopUpButton.
        """
        content = self.contentView()

        # Label
        y = 40 + 16
        label = NSTextField.alloc().initWithFrame_(NSMakeRect(15, y - 2, label_width, 24))
        label.setStringValue_(label_text)
        label.setAlignment_(2)
        label.setBezeled_(False)
        label.setDrawsBackground_(False)
        label.setEditable_(False)
        content.addSubview_(label)
        self.label = label

        # NSPopUpButton
        select = NSPopUpButton.alloc().initWithFrame_(NSMakeRect(input_start_x, y, input_width + 10, 24))
        select.setPullsDown_(False)
        # select.addItemsWithTitles_(options)
        select.selectItemAtIndex_(0)
        content.addSubview_(select)
        self.select = select

        # Save/Cancel Buttons
        x = input_start_x - 5
        cancel_btn = NSButton.alloc().initWithFrame_(NSMakeRect(x, 18, 80, 30))
        cancel_btn.setTitle_("Cancel")
        cancel_btn.setBezelStyle_(1)
        cancel_btn.setTarget_(self)
        cancel_btn.setAction_("cancel:")
        content.addSubview_(cancel_btn)

        save_btn = NSButton.alloc().initWithFrame_(NSMakeRect(x + 90, 18, 80, 30))
        save_btn.setTitle_(save_button_text)
        save_btn.setBezelStyle_(1)
        save_btn.setKeyEquivalent_("\r")
        save_btn.setTarget_(self)
        save_btn.setAction_("save:")
        content.addSubview_(save_btn)

    def update_items(self, items: list):
        """Update the items in the NSPopUpButton."""
        self.select.removeAllItems()
        self.select.addItemsWithTitles_(items)
        self.select.selectItemAtIndex_(0)

    def run(self):
        bring_app_to_front(self)

    def cancel_(self, _):
        self.close()

    def get_command(self, value: str):
        raise NotImplementedError("Subclasses must implement this method.")

    def save_(self, _):
        selectedItem = self.select.selectedItem()
        value = selectedItem.title() if selectedItem else None
        if not FormValidator.validate_empty_with_alert(value, self.label.stringValue().rstrip(':')):
            return

        output, returncode = run_susops(self.get_command(value))
        if returncode == 0:
            alert_foreground("Success", output)
            self.close()


class RemoveConnectionPanel(GenericSelectPanel):
    def get_command(self, value: str):
        return f"rm-connection {value}"


class RemoveDomainPanel(GenericSelectPanel):
    def get_command(self, value: str):
        return f"rm {value}"


class RemoveLocalForwardPanel(GenericSelectPanel):
    def get_command(self, value: str):
        # match by src
        pattern = r"\((\d+)\s"
        match = re.search(pattern, value)
        src = match.groups(1)[0]
        return f"rm -l {src}"


class RemoveRemoteForwardPanel(GenericSelectPanel):
    def get_command(self, value: str):
        # match by src
        pattern = r"\((\d+)\s"
        match = re.search(pattern, value)
        src = match.groups(1)[0]
        return f"rm -r {src}"


class AboutPanel(NSPanel):
    """A simple About dialog with icon, labels, and copyright."""

    def initWithContentRect_styleMask_backing_defer_(
            self, frame, style, backing, defer
    ):
        # call designated initializer
        self = objc.super(AboutPanel, self).initWithContentRect_styleMask_backing_defer_(
            frame, style, backing, defer
        )
        if not self:
            return None

        self.setHidesOnDeactivate_(False)

        # window styling
        self.setTitle_("")
        self.setLevel_(NSFloatingWindowLevel)
        content = self.contentView()

        # dimensions
        win_w = frame.size.width
        win_h = frame.size.height
        icon_size = 64

        # icon view centered at top
        x_icon = (win_w - icon_size) / 2
        y_icon = win_h - icon_size - 10
        icon_frame = NSMakeRect(x_icon, y_icon, icon_size, icon_size)
        image_view = NSImageView.alloc().initWithFrame_(icon_frame)
        img = NSImage.alloc().initByReferencingFile_("images/iconset/susops.iconset/icon_256x256.png")
        image_view.setImage_(img)
        content.addSubview_(image_view)

        # App name
        name_y = y_icon - 25
        name_field = NSTextField.alloc().initWithFrame_(NSMakeRect(0, name_y, win_w, 18))
        name_field.setStringValue_("SusOps")
        name_field.setAlignment_(1)
        name_field.setBezeled_(False)
        name_field.setDrawsBackground_(False)
        name_field.setEditable_(False)
        name_field.setFont_(NSFont.boldSystemFontOfSize_(14))
        content.addSubview_(name_field)

        # Versions
        ver_y = name_y - 20
        version_field = NSTextField.alloc().initWithFrame_(NSMakeRect(0, ver_y, win_w, 14))
        version_field.setStringValue_(f"Version {VERSION}")
        version_field.setAlignment_(1)
        version_field.setBezeled_(False)
        version_field.setDrawsBackground_(False)
        version_field.setEditable_(False)
        version_field.setFont_(NSFont.systemFontOfSize_(11))
        content.addSubview_(version_field)

        # Links (HTML attributed string)
        link_y = ver_y - 27
        link_text = (
            "<a href='https://github.com/mashb1t/susops-mac' style='text-decoration: none;'>GitHub</a> | "
            "<a href='https://github.com/mashb1t/susops-cli' style='text-decoration: none;'>CLI</a> | "
            "<a href='https://github.com/sponsors/mashb1t' style='text-decoration: none;'>Sponsor</a> | "
            "<a href='https://github.com/mashb1t/susops-mac/issues/new' style='text-decoration: none;'>Report a Bug</a>"
        )
        # convert HTML to attributed string
        html_bytes = link_text.encode('utf-8')
        data = NSData.alloc().initWithBytes_length_(html_bytes, len(html_bytes))
        opts = NSDictionary.dictionaryWithObject_forKey_(NSHTMLTextDocumentType, 'DocumentType')
        attr_str, _, _ = NSAttributedString.alloc() \
            .initWithData_options_documentAttributes_error_(
            data, opts, None, None
        )
        # adjust font size & center-align
        mutable = attr_str.mutableCopy()
        length = mutable.length()
        mutable.addAttribute_value_range_(
            NSFontAttributeName,
            NSFont.systemFontOfSize_(12),
            (0, length)
        )
        para = NSMutableParagraphStyle.alloc().init()
        para.setAlignment_(NSTextAlignmentCenter)
        mutable.addAttribute_value_range_(
            NSParagraphStyleAttributeName,
            para,
            (0, length)
        )

        label_color = NSColor.labelColor()
        # apply it across the entire string
        mutable.addAttribute_value_range_(
            NSForegroundColorAttributeName,
            label_color,
            (0, mutable.length())
        )

        links = NSTextField.alloc().initWithFrame_(NSMakeRect(0, link_y, win_w, 16))
        links.setAllowsEditingTextAttributes_(True)
        links.setSelectable_(True)
        links.setAlignment_(1)
        links.setBezeled_(False)
        links.setDrawsBackground_(False)
        links.setEditable_(False)
        links.setAttributedStringValue_(mutable)
        content.addSubview_(links)

        # Copyright
        copy_y = link_y - 25
        copyright = NSTextField.alloc().initWithFrame_(NSMakeRect(0, copy_y, win_w, 16))
        copyright.setStringValue_("Copyright © Manuel Schmid")
        copyright.setAlignment_(1)
        copyright.setBezeled_(False)
        copyright.setDrawsBackground_(False)
        copyright.setEditable_(False)
        copyright.setFont_(NSFont.systemFontOfSize_(11))
        content.addSubview_(copyright)

        return self

    def run(self):
        bring_app_to_front(self)


class AddConnectionPanel(GenericFieldPanel):

    def run(self):
        objc.super(AddConnectionPanel, self).run()

        try:
            ssh_hosts = get_ssh_hosts()
        except Exception as e:
            ssh_hosts = []

        self.host.removeAllItems()
        self.host.addItemsWithObjectValues_(ssh_hosts)

    def add_(self, _):
        tag = self.tag.stringValue().strip()
        host = self.host.stringValue().strip()
        socks_proxy_port = self.socks_proxy_port.stringValue().strip()

        if not FormValidator.validate_empty_with_alert(tag, "Connection Tag"):
            return

        if not FormValidator.validate_empty_with_alert(host, "SSH Host"):
            return

        # socks_proxy_port will be randomized on proxy start if empty
        if socks_proxy_port and not FormValidator.validate_port_with_alert(socks_proxy_port, "SOCKS Proxy Port"):
            return

        cmd = f"add-connection \"{tag}\" {host} {socks_proxy_port}"
        output, returncode = run_susops(cmd)
        if returncode == 0:
            alert_foreground("Success", output)
            self.close()
            self.tag.setStringValue_("")
            self.host.setStringValue_("")
            self.socks_proxy_port.setStringValue_("")


class AddHostPanel(GenericFieldPanel):

    def add_info_label(self, text, frame_width, frame_height):
        width = frame_width - 15 * 2
        height = 18 * 2
        frame_height -= 20 + height
        label = NSTextField.alloc().initWithFrame_(NSMakeRect(15, frame_height, width, height))
        label.setStringValue_(text)
        label.setAlignment_(1)
        label.setBezeled_(False)
        label.setDrawsBackground_(False)
        label.setEditable_(False)
        self.contentView().addSubview_(label)

    def add_(self, _):
        connection_item = self.connection.selectedItem()
        connection = connection_item.title() if connection_item else None
        host = self.host.stringValue().strip()

        if not FormValidator.validate_empty_with_alert(connection, "Connection"):
            return

        if not FormValidator.validate_empty_with_alert(host, "Host"):
            return

        cmd = f"-c \"{connection}\" add {host}"
        output, returncode = run_susops(cmd)
        if returncode == 0:
            alert_foreground("Success", output)
            self.close()
            self.host.setStringValue_("")


class LocalForwardPanel(GenericFieldPanel):
    def add_(self, _):

        connection_item = self.connection.selectedItem()
        connection = connection_item.title() if connection_item else None
        tag = self.tag.stringValue().strip()
        local_port = self.local_port_field.stringValue().strip()
        remote_port = self.remote_port_field.stringValue().strip()

        if not FormValidator.validate_empty_with_alert(connection, "Connection"):
            return

        if not FormValidator.validate_port_with_alert(local_port, "Local Port"):
            return

        if not FormValidator.validate_port_with_alert(remote_port, "Remote Port"):
            return

        cmd = f"-c \"{connection}\" add -l {local_port} {remote_port} \"{tag}\""
        output, returncode = run_susops(cmd)
        if returncode == 0:
            susops_app.show_restart_dialog("Success", output)
            self.close()
            self.tag.setStringValue_("")
            self.remote_port_field.setStringValue_("")
            self.local_port_field.setStringValue_("")


class RemoteForwardPanel(GenericFieldPanel):
    def add_(self, _):
        connection = self.connection.selectedItem().title()

        tag = self.tag.stringValue().strip()
        local_port = self.local_port_field.stringValue().strip()
        remote_port = self.remote_port_field.stringValue().strip()

        if not FormValidator.validate_port_with_alert(remote_port, "Remote Port"):
            return

        if not FormValidator.validate_port_with_alert(local_port, "Local Port"):
            return

        cmd = f"-c \"{connection}\" add -r {remote_port} {local_port} \"{tag}\""
        output, returncode = run_susops(cmd)
        if returncode == 0:
            susops_app.show_restart_dialog("Success", output)
            self.close()
            self.tag.setStringValue_("")
            self.local_port_field.setStringValue_("")
            self.remote_port_field.setStringValue_("")


if __name__ == "__main__":
    SusOpsApp().run()
