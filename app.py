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
    NSForegroundColorAttributeName, NSColor
)
from Foundation import NSBundle, NSData, NSDictionary

from version import VERSION


class Appearance(Enum):
    LIGHT = "light"
    DARK = "dark"


class ProcessState(Enum):
    INITIAL = "initial"
    RUNNING = "running"
    STOPPED_PARTIALLY = "stopped_partially"
    STOPPED = "stopped"
    ERROR = "error"


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


class SusOpsApp(rumps.App):
    def __init__(self, icon_dir=None):
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
        self.update_icon()

        self.settings_panel = None
        self.local_panel = None
        self.remote_panel = None
        self.about_panel = None

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
            rumps.MenuItem("Quit SusOps", callback=self.quit_app, key="q")
        ]

        self._check_timer = rumps.Timer(self.timer_check_state, 5)
        self._check_timer.start()

    def timer_check_state(self, _=None):
        # runs every 5s
        try:
            output, returncode = self._run_susops("ps", False)
        except subprocess.CalledProcessError:
            output, returncode = "Error running command", -1

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

        self.menu["Status"].title = f"SusOps is {self.process_state.value.replace("_", " ")}"
        self.menu["Status"].icon = os.path.join(self.images_dir, "status", self.process_state.value + ".svg")

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

    def appearanceChanged_(self, note):
        # Called when user switches between light/dark mode
        self.update_icon()

    def update_icon(self):
        state_value = "stopped" if self.process_state.value == "initial" else self.process_state.value

        # choose file based on state and appearance
        app = NSApplication.sharedApplication()
        appearance = app.effectiveAppearance().name()
        theme = 'light' if 'Dark' in appearance else 'dark'
        fname = f"logo_{theme}_{state_value}.svg"
        path = os.path.join(self.images_dir, "icons", fname)
        self.icon = path

    @staticmethod
    def _run_susops(command, show_alert=True):
        result = subprocess.run(f"{script} {command}", shell=True, capture_output=True, encoding="utf-8",
                                errors="ignore")
        if result.returncode != 0 and show_alert:
            alert_foreground("Error", result.stdout.strip())
        return result.stdout.strip(), result.returncode

    @staticmethod
    def load_config():
        ws = os.path.expanduser("~/.susops")
        defaults = {"ssh_host": "", "socks_port": "1080", "pac_port": "1081"}
        configs = {}
        for name in defaults:
            path = os.path.join(ws, name)
            try:
                with open(path) as f:
                    configs[name] = f.read().strip()
            except IOError:
                configs[name] = defaults[name]
        return configs

    def open_settings(self, _):
        NSApplication.sharedApplication().activateIgnoringOtherApps_(True)
        if self.settings_panel is None:
            frame = NSMakeRect(0, 0, 310, 190)
            style = (
                    NSWindowStyleMaskTitled
                    | NSWindowStyleMaskClosable
                    | NSWindowStyleMaskResizable
            )
            self.settings_panel = SettingsPanel.alloc().initWithContentRect_styleMask_backing_defer_(
                frame, style, NSBackingStoreBuffered, False
            )
            self.settings_panel.parent_app = self
        prefs = self.load_config()
        self.settings_panel.ssh_field.setStringValue_(prefs['ssh_host'])
        self.settings_panel.socks_field.setStringValue_(prefs['socks_port'])
        self.settings_panel.pac_field.setStringValue_(prefs['pac_port'])
        self.settings_panel.run()

    def add_domain(self, _):
        host = rumps.Window(
            "Enter domain to add (no protocol)\nThis domain and one level of subdomains will be added. to the PAC rules",
            "SusOps: Add Domain", ok="Add", cancel="Cancel", dimensions=(220, 20)).run().text
        if host:
            output, _ = self._run_susops(f"add {host}")
            rumps.notification("SusOps", "Add Domain", output)

    def add_local_forward(self, _):
        if not self.local_panel:
            frame = NSMakeRect(0, 0, 340, 150)
            style = (NSWindowStyleMaskTitled | NSWindowStyleMaskClosable | NSWindowStyleMaskResizable)
            self.local_panel = LocalForwardPanel.alloc().initWithContentRect_styleMask_backing_defer_(
                frame, style, NSBackingStoreBuffered, False
            )
            self.local_panel.setTitle_("Add Local Forward")
            self.local_panel.parent_app = self

        self.local_panel.configure_fields([
            ('remote_port_field', 'Forward Remote Port:'),
            ('local_port_field', 'To Local Port:'),
        ])
        self.local_panel.run()

    def add_remote_forward(self, _):
        if not self.remote_panel:
            frame = NSMakeRect(0, 0, 340, 150)
            style = (NSWindowStyleMaskTitled | NSWindowStyleMaskClosable | NSWindowStyleMaskResizable)
            self.remote_panel = RemoteForwardPanel.alloc().initWithContentRect_styleMask_backing_defer_(
                frame, style, NSBackingStoreBuffered, False
            )
            self.remote_panel.setTitle_("Add Remote Forward")
            self.remote_panel.parent_app = self

        self.remote_panel.configure_fields([
            ('local_port_field', 'Forward Local Port:'),
            ('remote_port_field', 'To Remote Port:'),
        ])
        self.remote_panel.run()

    def remove_domain(self, _):
        host = rumps.Window("Enter domain to remove (no protocol):", "SusOps: Remove Domain",
                            ok="Remove", cancel="Cancel", dimensions=(220, 20)).run().text
        if host:
            output, _ = self._run_susops(f"rm {host}")
            rumps.notification("SusOps", "Remove Domain", output)

    def remove_local_forward(self, _):
        port = rumps.Window("Enter port to remove:", "SusOps: Remove Local Forward",
                            ok="Remove", cancel="Cancel", dimensions=(220, 20)).run().text
        if port:
            output, _ = self._run_susops(f"rm -l {port}")
            rumps.notification("SusOps", "Remove Local Forward", output)

    def remove_remote_forward(self, _):
        port = rumps.Window("Enter port to remove:", "SusOps: Remove Remote Forward",
                            ok="Remove", cancel="Cancel", dimensions=(220, 20)).run().text
        if port:
            output, _ = self._run_susops(f"rm -r {port}")
            rumps.notification("SusOps", "Remove Remote Forward", output)

    def list_hosts(self, _):
        output, _ = self._run_susops("ls")
        alert_foreground("SusOps Hosts", output)

    def start_proxy(self, _):
        """Start the proxy in a fully detached background session using setsid."""
        config = self.load_config()
        if not config['ssh_host']:
            alert_foreground("Startup failed", "Please set the SSH Host in Settings")
            self.open_settings(None)
            return
        cmd = f"{script} start {config['ssh_host']} {config['socks_port']} {config['pac_port']}"
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
        output, _ = self._run_susops("stop --keep-ports")
        self.timer_check_state()

    def restart_proxy(self, _):
        p = self.load_config()
        cmd = f"restart {p['ssh_host']} {p['socks_port']} {p['pac_port']}"
        output, _ = self._run_susops(cmd)
        self.timer_check_state()

    def check_status(self, _):
        output, _ = self._run_susops("ps", False)
        alert_foreground("SusOps Status", output)

    def test_any(self, _):
        host = rumps.Window("Enter hostname or port to test: ", "SusOps: Test Any",
                            ok="Test", cancel="Cancel", dimensions=(220, 20)).run().text
        if host:
            output, _ = self._run_susops(f"test {host}", False)
            alert_foreground("SusOps Test", output)

    def test_all(self, _):
        output, _ = self._run_susops("test --all", False)
        alert_foreground("SusOps Test All", output)

    def launch_chrome(self, _):
        output, _ = self._run_susops("chrome", False)

    def launch_chrome_proxy_settings(self, _):
        output, _ = self._run_susops("chrome-proxy-settings", False)

    def launch_firefox(self, _):
        output, _ = self._run_susops("firefox", False)

    def reset(self, _):
        result = alert_foreground(
            "Reset Everything?",
            "This will stop susops and remove all of its configs. You will have to reconfigure the ssh host as well as ports.\n\nAre you sure?",
            ok="Yes", cancel="No"
        )

        if result == 1:
            self._run_susops("reset --force", False)

    def open_about(self, _):
        if not hasattr(self, 'about_panel') or self.about_panel is None:
            frame = NSMakeRect(0, 0, 280, 190)
            style = (NSWindowStyleMaskTitled | NSWindowStyleMaskClosable)
            self.about_panel = AboutPanel.alloc().initWithContentRect_styleMask_backing_defer_(
                frame, style, NSBackingStoreBuffered, False
            )
            self.about_panel.parent_app = self
        self.about_panel.run()

    def quit_app(self, _):
        self._run_susops("stop --keep-ports", False)
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

        self.setTitle_("SusOps Settings")
        self.setLevel_(NSFloatingWindowLevel)

        content = self.contentView()

        # --- SSH Host ---
        self.ssh_label = NSTextField.alloc().initWithFrame_(NSMakeRect(20, 140, 100, 24))
        self.ssh_label.setStringValue_("SSH Host:")
        self.ssh_label.setBezeled_(False)
        self.ssh_label.setDrawsBackground_(False)
        self.ssh_label.setEditable_(False)
        content.addSubview_(self.ssh_label)

        self.ssh_field = NSTextField.alloc().initWithFrame_(NSMakeRect(130, 140, 160, 24))
        content.addSubview_(self.ssh_field)

        # --- SOCKS Port ---
        self.socks_label = NSTextField.alloc().initWithFrame_(NSMakeRect(20, 100, 100, 24))
        self.socks_label.setStringValue_("SOCKS Port:")
        self.socks_label.setBezeled_(False)
        self.socks_label.setDrawsBackground_(False)
        self.socks_label.setEditable_(False)
        content.addSubview_(self.socks_label)

        self.socks_field = NSTextField.alloc().initWithFrame_(NSMakeRect(130, 100, 160, 24))
        content.addSubview_(self.socks_field)

        # --- PAC Port ---
        self.pac_label = NSTextField.alloc().initWithFrame_(NSMakeRect(20, 60, 100, 24))
        self.pac_label.setStringValue_("PAC Port:")
        self.pac_label.setBezeled_(False)
        self.pac_label.setDrawsBackground_(False)
        self.pac_label.setEditable_(False)
        content.addSubview_(self.pac_label)

        self.pac_field = NSTextField.alloc().initWithFrame_(NSMakeRect(130, 60, 160, 24))
        content.addSubview_(self.pac_field)

        # --- Save/Cancel Buttons ---
        cancel_btn = NSButton.alloc().initWithFrame_(NSMakeRect(125, 18, 80, 30))
        cancel_btn.setTitle_("Cancel")
        cancel_btn.setBezelStyle_(1)
        cancel_btn.setTarget_(self)
        cancel_btn.setAction_("cancelSettings:")
        content.addSubview_(cancel_btn)

        save_btn = NSButton.alloc().initWithFrame_(NSMakeRect(215, 18, 80, 30))
        save_btn.setTitle_("Save")
        save_btn.setBezelStyle_(1)
        save_btn.setTarget_(self)
        save_btn.setAction_("saveSettings:")
        content.addSubview_(save_btn)

        return self

    def saveSettings_(self, sender):
        ws = os.path.expanduser("~/.susops")
        os.makedirs(ws, exist_ok=True)
        # write prefs with newline
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

        self.close()
        restart = alert_foreground(
            "Settings Saved",
            "Settings will be applied on next proxy service start.\n\nRestart proxy service now?",
            ok="Yes", cancel="No"
        )

        if restart == 1:
            self.parent_app.restart_proxy(None)

    def cancelSettings_(self, sender):
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
        cancel_btn = NSButton.alloc().initWithFrame_(NSMakeRect(155, 18, 80, 30))
        cancel_btn.setTitle_("Cancel")
        cancel_btn.setBezelStyle_(1)
        cancel_btn.setTarget_(self)
        cancel_btn.setAction_("cancel:")
        content.addSubview_(cancel_btn)

        add_btn = NSButton.alloc().initWithFrame_(NSMakeRect(245, 18, 80, 30))
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
            lbl = NSTextField.alloc().initWithFrame_(NSMakeRect(20, y, 140, 24))
            lbl.setStringValue_(label)
            lbl.setBezeled_(False)
            lbl.setDrawsBackground_(False)
            lbl.setEditable_(False)
            self.contentView().addSubview_(lbl)

            fld = NSTextField.alloc().initWithFrame_(NSMakeRect(160, y, 160, 24))
            self.contentView().addSubview_(fld)
            setattr(self, attr, fld)
            y -= 40

    def run(self):
        NSApplication.sharedApplication().activateIgnoringOtherApps_(True)
        self.center()
        self.makeKeyAndOrderFront_(None)

    def cancel_(self, sender):
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

        # load icon from bundle resources
        bundle = NSBundle.mainBundle()
        res_path = bundle.resourcePath()
        img_path = f"images/icons/logo_dark_stopped_partially.svg"
        # icon view centered at top
        x_icon = (win_w - icon_size) / 2
        y_icon = win_h - icon_size - 10
        icon_frame = NSMakeRect(x_icon, y_icon, icon_size, icon_size)
        image_view = NSImageView.alloc().initWithFrame_(icon_frame)
        img = NSImage.alloc().initByReferencingFile_(img_path)
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
    def add_(self, sender):
        if (self.local_port_field.stringValue().isdigit() and
                self.remote_port_field.stringValue().isdigit()):
            cmd = f"add -l {self.remote_port_field.stringValue()} {self.local_port_field.stringValue()}"
            out, _ = self.parent_app.run_susops(cmd)
            rumps.notification("SusOps", "Local Forward Added", out)
        self.close()


class RemoteForwardPanel(TwoFieldPanel):
    def add_(self, sender):
        if (self.remote_port_field.stringValue().isdigit() and
                self.local_port_field.stringValue().isdigit()):
            cmd = f"add -r {self.local_port_field.stringValue()} {self.remote_port_field.stringValue()}"
            out, _ = self.parent_app.run_susops(cmd)
            rumps.notification("SusOps", "Remote Forward Added", out)
        self.close()


if __name__ == "__main__":
    SusOpsApp().run()
