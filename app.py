import os
import subprocess
import sys
from enum import Enum

import objc
import rumps
from AppKit import (
    NSWindowStyleMaskTitled,
    NSWindowStyleMaskClosable,
    NSWindowStyleMaskResizable,
    NSBackingStoreBuffered,
    NSFloatingWindowLevel
)
from Cocoa import (
    NSPanel, NSTextField, NSMakeRect,
    NSButton, NSApplication, NSDistributedNotificationCenter,
    NSImageView, NSImage, NSFont, NSAttributedString, NSHTMLTextDocumentType,
    NSFontAttributeName, NSMutableParagraphStyle, NSParagraphStyleAttributeName, NSTextAlignmentCenter,
    NSForegroundColorAttributeName, NSColor, NSRadioButton, NSOnState, NSOffState,
    NSSegmentedControl, NSSegmentSwitchTrackingSelectOne, NSRegularControlSize, NSImageScaleProportionallyDown,
    NSSwitchButton
)
from Foundation import NSBundle, NSData, NSDictionary

from version import VERSION


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
    COG = "COG"
    COLORED_GLASSES = "COLORED_GLASSES"
    COLORED_S = "COLORED_S"


DEFAULT_LOGO_STYLE = LogoStyle.COLORED_GLASSES


def get_appearance() -> Appearance:
    app = NSApplication.sharedApplication()
    appearance = app.effectiveAppearance().name()
    return Appearance.DARK if Appearance.DARK.value.lower() in appearance.lower() else Appearance.LIGHT


def get_logo_style_image(style: LogoStyle, state: ProcessState = ProcessState.STOPPED_PARTIALLY, appearance: Appearance = None) -> str:
    appearance = appearance or get_appearance()
    appearance = Appearance.LIGHT if appearance == Appearance.DARK else Appearance.DARK
    filetype = "svg" if style == LogoStyle.COG else "png"
    return os.path.join("images", "icons", style.value.lower(), appearance.value.lower(), f"{state.value.lower()}.{filetype}")


def alert_foreground(title, message, ok=None, cancel=None, other=None, icon_path=None) -> int:
    NSApplication.sharedApplication().activateIgnoringOtherApps_(True)
    return rumps.alert(title, message, ok, cancel, other, icon_path)


def resource_path(rel_path):
    # on macOS bundle, resources are in Contents/Resources
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        base = sys._MEIPASS
    else:
        # running normally: project root
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, rel_path)


script = resource_path(os.path.join('susops-cli', 'susops.sh'))


# Global instance of the app
susops_app = None  # type: SusOpsApp|None


class SusOpsApp(rumps.App):
    def __init__(self, icon_dir=None):
        global susops_app
        susops_app = self
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
        self._local_panel = None
        self._remote_panel = None
        self._about_panel = None

        self.menu = [
            rumps.MenuItem("Status", callback=self.check_status),
            None,
            rumps.MenuItem("Settings…", callback=self.open_settings, key=","),
            None,
            (rumps.MenuItem("Add"), [
                rumps.MenuItem("Add Domain", callback=self.add_domain),
                rumps.MenuItem("Add Local Forward", callback=self.add_local_forward),
                rumps.MenuItem("Add Remote Forward", callback=self.add_remote_forward),
            ]),
            (rumps.MenuItem("Remove"), [
                rumps.MenuItem("Remove Domain", callback=self.remove_domain),
                rumps.MenuItem("Remove Local Forward", callback=self.remove_local_forward),
                rumps.MenuItem("Remove Remote Forward", callback=self.remove_remote_forward),
            ]),
            rumps.MenuItem("List All", callback=self.list_hosts),
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
            rumps.MenuItem("About", callback=self.open_about),
            rumps.MenuItem("Quit", callback=self.quit_app, key="q")
        ]

        self._check_timer = rumps.Timer(self.timer_check_state, 5)
        self._check_timer.start()

    def timer_check_state(self, _=None):
        # runs every 5s
        try:
            output, returncode = self.run_susops("ps", False)
        except subprocess.CalledProcessError:
            output, returncode = "Error running command", -1

        if not output:
            returncode = -1

        match returncode:
            case 0:
                new_state = ProcessState.RUNNING
            case 1:
                new_state = ProcessState.STOPPED_PARTIALLY
            case 2:
                new_state = ProcessState.STOPPED
            case _:
                new_state = ProcessState.ERROR

        if new_state == self.process_state:
            return

        self.process_state = new_state
        self.update_icon()

        self.menu["Status"].title = f"SusOps is {self.process_state.value.lower().replace("_", " ")}"
        self.menu["Status"].icon = os.path.join(self.images_dir, "status", self.process_state.value.lower() + ".svg")

        match self.process_state:
            case ProcessState.RUNNING:
                self.menu["Start Proxy"].set_callback(None)
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
    def run_susops(command, show_alert=True):
        result = subprocess.run(f"{script} {command}", shell=True, capture_output=True, encoding="utf-8",
                                errors="ignore")
        if result.returncode != 0 and show_alert:
            alert_foreground("Error", result.stdout.strip())
        return result.stdout.strip(), result.returncode

    @staticmethod
    def load_config():
        ws = os.path.expanduser("~/.susops")
        defaults = {"ssh_host": "", "socks_port": "1080", "pac_port": "1081", "logo_style": DEFAULT_LOGO_STYLE.value}
        configs = {}
        for name in defaults:
            path = os.path.join(ws, name)
            try:
                with open(path) as f:
                    configs[name] = f.read().strip()
            except IOError:
                configs[name] = defaults[name]

        # check if logo_style is valid
        if configs['logo_style'] not in LogoStyle.__members__:
            configs['logo_style'] = DEFAULT_LOGO_STYLE.value
            with open(os.path.join(ws, "logo_style"), "w") as f:
                f.write(configs['logo_style'])
        return configs

    def open_settings(self, _):
        NSApplication.sharedApplication().activateIgnoringOtherApps_(True)
        if self._settings_panel is None:
            frame = NSMakeRect(0, 0, 310, 260)
            style = (
                    NSWindowStyleMaskTitled
                    | NSWindowStyleMaskClosable
                    | NSWindowStyleMaskResizable
            )
            self._settings_panel = SettingsPanel.alloc().initWithContentRect_styleMask_backing_defer_(
                frame, style, NSBackingStoreBuffered, False
            )
        self.config = self.load_config()
        self._settings_panel.ssh_field.setStringValue_(self.config['ssh_host'])
        self._settings_panel.socks_field.setStringValue_(self.config['socks_port'])
        self._settings_panel.pac_field.setStringValue_(self.config['pac_port'])

        app_path = os.path.basename(NSBundle.mainBundle().bundlePath())
        app_name = os.path.splitext(os.path.basename(app_path))[0]
        script = 'tell application "System Events" to get name of every login item'
        try:
            out = subprocess.check_output(["osascript", "-e", script])
            enabled = app_name in out.decode()
        except:
            enabled = False
        self._settings_panel.launch_checkbox.setState_(NSOnState if enabled else NSOffState)

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

    def add_domain(self, sender, default_text=''):
        result = rumps.Window(
            "Enter domain to add (no protocol)\nThis domain and one level of subdomains will be added. to the PAC rules",
            "Add Domain", default_text, "Add", "Cancel", (220, 20)).run()

        if result.clicked == 0:
            return

        host = result.text.strip()
        if not host:
            alert_foreground("Error", "Domain cannot be empty")
            self.add_domain(sender)
            return

        output, returncode = self.run_susops(f"add {host}")
        if returncode == 0:
            alert_foreground("Success", output)
        else:
            self.add_domain(sender, result.text)

    def add_local_forward(self, _):
        if not self._local_panel:
            frame = NSMakeRect(0, 0, 350, 150)
            style = (NSWindowStyleMaskTitled | NSWindowStyleMaskClosable | NSWindowStyleMaskResizable)
            self._local_panel = LocalForwardPanel.alloc().initWithContentRect_styleMask_backing_defer_(
                frame, style, NSBackingStoreBuffered, False
            )
            self._local_panel.setTitle_("Add Local Forward")

        self._local_panel.configure_fields([
            ('remote_port_field', 'Make Remote Port:'),
            ('local_port_field', 'Available on Local Port:'),
        ])
        self._local_panel.run()

    def add_remote_forward(self, _):
        if not self._remote_panel:
            frame = NSMakeRect(0, 0, 350, 150)
            style = (NSWindowStyleMaskTitled | NSWindowStyleMaskClosable | NSWindowStyleMaskResizable)
            self._remote_panel = RemoteForwardPanel.alloc().initWithContentRect_styleMask_backing_defer_(
                frame, style, NSBackingStoreBuffered, False
            )
            self._remote_panel.setTitle_("Add Remote Forward")
        self._remote_panel.configure_fields([
            ('local_port_field', 'Make Local Port:'),
            ('remote_port_field', 'Available on Remote Port:'),
        ])
        self._remote_panel.run()

    def remove_domain(self, sender, default_text=''):
        result = rumps.Window("Enter domain to remove (without protocol):",
                              "Remove Domain", default_text, "Remove", "Cancel", (220, 20)).run()

        if result.clicked == 0:
            return

        host = result.text.strip()
        if not host:
            alert_foreground("Error", "Domain cannot be empty")
            self.remove_domain(sender)
            return

        output, returncode = self.run_susops(f"rm {host}")
        if returncode != 0:
            alert_foreground("Success", output)
            return self.remove_domain(sender, host)
        else:
            self.show_restart_dialog("Success", output)

    def remove_local_forward(self, sender, default_text=''):
        result = rumps.Window("Enter port to remove:", "Remove Local Forward",
                              default_text, ok="Remove", cancel="Cancel", dimensions=(220, 20)).run()

        if result.clicked == 0:
            return

        port = result.text.strip()

        if not port:
            alert_foreground("Error", "Port cannot be empty")
            self.remove_local_forward(sender)
            return

        output, returncode = self.run_susops(f"rm -l {port}")
        if returncode != 0:
            return self.remove_local_forward(sender, port)
        else:
            self.show_restart_dialog("Success", output)

    def remove_remote_forward(self, sender, default_text=''):
        result = rumps.Window("Enter port to remove:", "Remove Remote Forward",
                              default_text, ok="Remove", cancel="Cancel", dimensions=(220, 20)).run()

        if result.clicked == 0:
            return

        port = result.text.strip()

        if not port:
            alert_foreground("Error", "Port cannot be empty")
            self.remove_remote_forward(sender)
            return

        output, returncode = self.run_susops(f"rm -r {port}")
        if returncode != 0:
            return self.remove_remote_forward(sender, port)
        else:
            self.show_restart_dialog("Success", output)

    def list_hosts(self, _):
        output, _ = self.run_susops("ls")
        alert_foreground("Domains & Forwards", output)

    def start_proxy(self, _):
        """Start the proxy in a fully detached background session using setsid."""
        self.config = self.load_config()
        if not self.config['ssh_host']:
            alert_foreground("Startup failed", "Please set the SSH Host in Settings")
            self.open_settings(None)
            return
        cmd = f"{script} start {self.config['ssh_host']} {self.config['socks_port']} {self.config['pac_port']}"
        shell = os.environ.get('SHELL', '/bin/bash')
        try:
            # Launch using bash -lc and detach from UI process
            subprocess.Popen([
                shell, '-c', cmd
            ], stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                preexec_fn=os.setsid,
                close_fds=True)
            self.timer_check_state()
        except Exception as e:
            alert_foreground("Error starting proxy", str(e))

    def stop_proxy(self, _):
        output, _ = self.run_susops("stop --keep-ports")
        self.timer_check_state()

    def restart_proxy(self, _):
        self.config = self.load_config()
        cmd = f"restart {self.config['ssh_host']} {self.config['socks_port']} {self.config['pac_port']}"
        output, _ = self.run_susops(cmd)
        self.timer_check_state()

    def check_status(self, _):
        output, _ = self.run_susops("ps", False)
        alert_foreground("SusOps Status", output)

    def test_any(self, _):
        host = rumps.Window("Enter domain or port to test: ", "Test Any",
                            ok="Test", cancel="Cancel", dimensions=(220, 20)).run().text
        if host:
            output, _ = self.run_susops(f"test {host}", False)
            alert_foreground("SusOps Test", output)

    def test_all(self, _):
        output, _ = self.run_susops("test --all", False)
        alert_foreground("SusOps Test All", output)

    def launch_chrome(self, _):
        output, _ = self.run_susops("chrome", False)

    def launch_chrome_proxy_settings(self, _):
        output, _ = self.run_susops("chrome-proxy-settings", False)

    def launch_firefox(self, _):
        output, _ = self.run_susops("firefox", False)

    def reset(self, _):
        result = alert_foreground(
            "Reset Everything?",
            "This will stop SusOps and remove all of its configs. You will have to reconfigure the ssh host as well as ports.\n\nAre you sure?",
            ok="Reset Everything", cancel="Cancel"
        )

        if result == 1:
            self.run_susops("reset --force", False)

    def open_about(self, _):
        if self._about_panel is None:
            frame = NSMakeRect(0, 0, 280, 190)
            style = (NSWindowStyleMaskTitled | NSWindowStyleMaskClosable)
            self._about_panel = AboutPanel.alloc().initWithContentRect_styleMask_backing_defer_(
                frame, style, NSBackingStoreBuffered, False
            )
        self._about_panel.run()

    def quit_app(self, _):
        self.run_susops("stop --keep-ports", False)
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

        self.setTitle_("Settings")
        self.setLevel_(NSFloatingWindowLevel)
        content = self.contentView()
        win_h = frame.size.height

        # --- Launch at Login Checkbox ---
        y = win_h - 40
        self.launch_checkbox = NSButton.alloc().initWithFrame_(NSMakeRect(130, y, 160, 24))
        self.launch_checkbox.setButtonType_(NSSwitchButton)
        self.launch_checkbox.setTitle_("Launch at Login")

        self.launch_checkbox.setTarget_(self)
        # self.launch_checkbox.setAction_("toggleLaunchAtLogin:")
        content.addSubview_(self.launch_checkbox)

        # --- Logo Style ---
        y -= 40
        self.logo_label = NSTextField.alloc().initWithFrame_(NSMakeRect(20, y - 4, 100, 24))
        self.logo_label.setStringValue_("Logo Style:")
        self.logo_label.setAlignment_(2)
        self.logo_label.setBezeled_(False)
        self.logo_label.setDrawsBackground_(False)
        self.logo_label.setEditable_(False)
        content.addSubview_(self.logo_label)

        self.segmented_icons = NSSegmentedControl.alloc().initWithFrame_(NSMakeRect(130, y, 160, 24))
        self.segmented_icons.setSegmentCount_(len(LogoStyle))
        self.segmented_icons.setTrackingMode_(NSSegmentSwitchTrackingSelectOne)
        self.segmented_icons.setControlSize_(NSRegularControlSize)

        self.update_appearance()

        self.segmented_icons.setTarget_(self)
        self.segmented_icons.setAction_("segmentedIconsChange:")  # define this method to handle clicks
        content.addSubview_(self.segmented_icons)

        # --- SSH Host ---
        y -= 40
        self.ssh_label = NSTextField.alloc().initWithFrame_(NSMakeRect(20, y - 4, 100, 24))
        self.ssh_label.setStringValue_("SSH Host:")
        self.ssh_label.setAlignment_(2)
        self.ssh_label.setBezeled_(False)
        self.ssh_label.setDrawsBackground_(False)
        self.ssh_label.setEditable_(False)
        content.addSubview_(self.ssh_label)

        self.ssh_field = NSTextField.alloc().initWithFrame_(NSMakeRect(130, y, 160, 24))
        content.addSubview_(self.ssh_field)

        # --- SOCKS Port ---
        y -= 40
        self.socks_label = NSTextField.alloc().initWithFrame_(NSMakeRect(20, y - 4, 100, 24))
        self.socks_label.setStringValue_("SOCKS Port:")
        self.socks_label.setAlignment_(2)
        self.socks_label.setBezeled_(False)
        self.socks_label.setDrawsBackground_(False)
        self.socks_label.setEditable_(False)
        content.addSubview_(self.socks_label)

        self.socks_field = NSTextField.alloc().initWithFrame_(NSMakeRect(130, y, 160, 24))
        content.addSubview_(self.socks_field)

        # --- PAC Port ---
        y -= 40
        self.pac_label = NSTextField.alloc().initWithFrame_(NSMakeRect(20, y - 4, 100, 24))
        self.pac_label.setStringValue_("PAC Port:")
        self.pac_label.setAlignment_(2)
        self.pac_label.setBezeled_(False)
        self.pac_label.setDrawsBackground_(False)
        self.pac_label.setEditable_(False)
        content.addSubview_(self.pac_label)

        self.pac_field = NSTextField.alloc().initWithFrame_(NSMakeRect(130, y, 160, 24))
        content.addSubview_(self.pac_field)

        # --- Save/Cancel Buttons ---
        y -= 40
        cancel_btn = NSButton.alloc().initWithFrame_(NSMakeRect(125, y, 80, 30))
        cancel_btn.setTitle_("Cancel")
        cancel_btn.setBezelStyle_(1)
        cancel_btn.setTarget_(self)
        cancel_btn.setAction_("cancelSettings:")
        content.addSubview_(cancel_btn)

        save_btn = NSButton.alloc().initWithFrame_(NSMakeRect(215, y, 80, 30))
        save_btn.setTitle_("Save")
        save_btn.setBezelStyle_(1)
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
        self.toggleLaunchAtLogin_(self.launch_checkbox)

        ws = os.path.expanduser("~/.susops")
        os.makedirs(ws, exist_ok=True)
        for name, label, field in (("ssh_host", self.ssh_label, self.ssh_field),
                                   ("socks_port", self.socks_label, self.socks_field),
                                   ("pac_port", self.pac_label, self.pac_field)):
            value_stripped = field.stringValue().strip()
            if not value_stripped:
                alert_foreground("Error", f"Field {label.stringValue().replace(":", "")} cannot be empty")
                return
            val = str(value_stripped) + "\n"
            with open(os.path.join(ws, name), "w") as f:
                f.write(val)

        selected_index = self.segmented_icons.selectedSegment()
        selected_style = list(LogoStyle)[selected_index]
        with open(os.path.join(ws, "logo_style"), "w") as f:
            f.write(selected_style.value)

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
        NSApplication.sharedApplication().activateIgnoringOtherApps_(True)
        self.center()
        self.makeKeyAndOrderFront_(None)


class TwoFieldPanel(NSPanel):

    def initWithContentRect_styleMask_backing_defer_(
            self, frame, style, backing, defer
    ):
        self = objc.super(TwoFieldPanel, self).initWithContentRect_styleMask_backing_defer_(
            frame, style, backing, defer
        )
        if not self:
            return None

        self.setLevel_(NSFloatingWindowLevel)
        content = self.contentView()

        # --- Save/Cancel Buttons ---
        cancel_btn = NSButton.alloc().initWithFrame_(NSMakeRect(165, 18, 80, 30))
        cancel_btn.setTitle_("Cancel")
        cancel_btn.setBezelStyle_(1)
        cancel_btn.setTarget_(self)
        cancel_btn.setAction_("cancel:")
        content.addSubview_(cancel_btn)

        add_btn = NSButton.alloc().initWithFrame_(NSMakeRect(255, 18, 80, 30))
        add_btn.setTitle_("Add")
        add_btn.setBezelStyle_(1)
        add_btn.setTarget_(self)
        add_btn.setAction_("add:")
        content.addSubview_(add_btn)

        return self

    def configure_fields(self, field_defs):
        """
        field_defs = [(attr_name, label_text), ...]   # order = top → bottom
        Builds one label/field row per entry, 40 px vertical spacing.
        """
        # purge any old dynamic subviews (labels / text-fields)
        for view in list(self.contentView().subviews()):
            if isinstance(view, NSTextField) and view.isEditable():
                view.removeFromSuperview()
            elif isinstance(view, NSTextField) and not view.isEditable():
                if view.stringValue().endswith(':'):
                    view.removeFromSuperview()

        y = 100
        for attr, label in field_defs:
            lbl = NSTextField.alloc().initWithFrame_(NSMakeRect(15, y - 4, 150, 24))
            lbl.setStringValue_(label)
            lbl.setAlignment_(2)
            lbl.setBezeled_(False)
            lbl.setDrawsBackground_(False)
            lbl.setEditable_(False)
            self.contentView().addSubview_(lbl)

            fld = NSTextField.alloc().initWithFrame_(NSMakeRect(170, y, 160, 24))
            self.contentView().addSubview_(fld)
            setattr(self, attr, fld)
            y -= 40

    @staticmethod
    def check_port_range(port, label):
        if not port.isdigit() or not (1 <= int(port) <= 65535):
            alert_foreground("Error", f"{label} must be a valid port between 1 and 65535")
            return False
        return True

    def run(self):
        NSApplication.sharedApplication().activateIgnoringOtherApps_(True)
        self.center()
        self.makeKeyAndOrderFront_(None)

    def cancel_(self, _):
        self.close()


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
        self.image_view = NSImageView.alloc().initWithFrame_(icon_frame)

        img_path = get_logo_style_image(LogoStyle.COG, ProcessState.STOPPED_PARTIALLY, Appearance.LIGHT)
        img = NSImage.alloc().initByReferencingFile_(img_path)
        self.image_view.setImage_(img)

        content.addSubview_(self.image_view)

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
            "<a href='https://github.com/sponsors/mashb1t' style='text-decoration: none;'>Sponsor</a>"
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
        NSApplication.sharedApplication().activateIgnoringOtherApps_(True)
        self.center()
        self.makeKeyAndOrderFront_(None)


class LocalForwardPanel(TwoFieldPanel):
    def add_(self, _):
        if not self.check_port_range(self.remote_port_field.stringValue(), "Remote Port"):
            return

        if not self.check_port_range(self.local_port_field.stringValue(), "Local Port"):
            return

        cmd = f"add -l {self.local_port_field.stringValue()} {self.remote_port_field.stringValue()}"
        output, returncode = susops_app.run_susops(cmd)
        if returncode == 0:
            susops_app.show_restart_dialog("Success", output)
            self.close()


class RemoteForwardPanel(TwoFieldPanel):
    def add_(self, _):
        if not self.check_port_range(self.local_port_field.stringValue(), "Local Port"):
            return

        if not self.check_port_range(self.remote_port_field.stringValue(), "Remote Port"):
            return

        cmd = f"add -r {self.remote_port_field.stringValue()} {self.local_port_field.stringValue()}"
        output, returncode = susops_app.run_susops(cmd)
        if returncode == 0:
            susops_app.show_restart_dialog("Success", output)
            self.close()


if __name__ == "__main__":
    SusOpsApp().run()
