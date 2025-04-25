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
    NSButton, NSApplication, NSDistributedNotificationCenter
)


class Appearance(Enum):
    LIGHT = "light"
    DARK = "dark"


class ProcessState(Enum):
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


script = resource_path('susops/susops.sh')


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
        save_btn = NSButton.alloc().initWithFrame_(NSMakeRect(135, 18, 80, 30))
        save_btn.setTitle_("Save")
        save_btn.setBezelStyle_(1)
        save_btn.setTarget_(self)
        save_btn.setAction_("save:")
        content.addSubview_(save_btn)

        cancel_btn = NSButton.alloc().initWithFrame_(NSMakeRect(225, 18, 80, 30))
        cancel_btn.setTitle_("Cancel")
        cancel_btn.setBezelStyle_(1)
        cancel_btn.setTarget_(self)
        cancel_btn.setAction_("cancel:")
        content.addSubview_(cancel_btn)

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
            lbl = NSTextField.alloc().initWithFrame_(NSMakeRect(20, y, 120, 24))
            lbl.setStringValue_(label)
            lbl.setBezeled_(False)
            lbl.setDrawsBackground_(False)
            lbl.setEditable_(False)
            self.contentView().addSubview_(lbl)

            fld = NSTextField.alloc().initWithFrame_(NSMakeRect(140, y, 160, 24))
            self.contentView().addSubview_(fld)
            setattr(self, attr, fld)
            y -= 40

    def run(self):
        self.center()
        self.makeKeyAndOrderFront_(None)

    def cancel_(self, sender):
        self.close()


class LocalForwardPanel(TwoFieldPanel):
    def save_(self, sender):
        if (self.local_port_field.stringValue().isdigit() and
                self.remote_port_field.stringValue().isdigit()):
            cmd = f"add -r {self.remote_port_field.stringValue()} {self.local_port_field.stringValue()}"
            out, _ = self.parent_app._run_susops(cmd)
            rumps.notification("SusOps", "Remote Forward Added", out)
        self.close()


class RemoteForwardPanel(TwoFieldPanel):
    def save_(self, sender):
        if (self.remote_port_field.stringValue().isdigit() and
                self.local_port_field.stringValue().isdigit()):
            cmd = f"add -r {self.local_port_field.stringValue()} {self.remote_port_field.stringValue()}"
            out, _ = self.parent_app._run_susops(cmd)
            rumps.notification("SusOps", "Local Forward Added", out)
        self.close()


class PrefsPanel(NSPanel):
    """A floating panel with SSH Host, SOCKS Port & PAC Port fields plus Save/Cancel."""

    def initWithContentRect_styleMask_backing_defer_(
            self, frame, style, backing, defer
    ):
        self = objc.super(PrefsPanel, self).initWithContentRect_styleMask_backing_defer_(
            frame, style, backing, defer
        )
        if not self:
            return None

        self.setTitle_("SusOps Preferences")
        self.setLevel_(NSFloatingWindowLevel)

        content = self.contentView()

        # --- SSH Host ---
        lbl1 = NSTextField.alloc().initWithFrame_(NSMakeRect(20, 140, 100, 24))
        lbl1.setStringValue_("SSH Host:")
        lbl1.setBezeled_(False)
        lbl1.setDrawsBackground_(False)
        lbl1.setEditable_(False)
        content.addSubview_(lbl1)

        self.ssh_field = NSTextField.alloc().initWithFrame_(NSMakeRect(130, 140, 160, 24))
        content.addSubview_(self.ssh_field)

        # --- SOCKS Port ---
        lbl2 = NSTextField.alloc().initWithFrame_(NSMakeRect(20, 100, 100, 24))
        lbl2.setStringValue_("SOCKS Port:")
        lbl2.setBezeled_(False)
        lbl2.setDrawsBackground_(False)
        lbl2.setEditable_(False)
        content.addSubview_(lbl2)

        self.socks_field = NSTextField.alloc().initWithFrame_(NSMakeRect(130, 100, 160, 24))
        content.addSubview_(self.socks_field)

        # --- PAC Port ---
        lbl3 = NSTextField.alloc().initWithFrame_(NSMakeRect(20, 60, 100, 24))
        lbl3.setStringValue_("PAC Port:")
        lbl3.setBezeled_(False)
        lbl3.setDrawsBackground_(False)
        lbl3.setEditable_(False)
        content.addSubview_(lbl3)

        self.pac_field = NSTextField.alloc().initWithFrame_(NSMakeRect(130, 60, 160, 24))
        content.addSubview_(self.pac_field)

        # --- Save/Cancel Buttons ---
        save_btn = NSButton.alloc().initWithFrame_(NSMakeRect(125, 18, 80, 30))
        save_btn.setTitle_("Save")
        save_btn.setBezelStyle_(1)
        save_btn.setTarget_(self)
        save_btn.setAction_("savePreferences:")
        content.addSubview_(save_btn)

        cancel_btn = NSButton.alloc().initWithFrame_(NSMakeRect(215, 18, 80, 30))
        cancel_btn.setTitle_("Cancel")
        cancel_btn.setBezelStyle_(1)
        cancel_btn.setTarget_(self)
        cancel_btn.setAction_("cancelPreferences:")
        content.addSubview_(cancel_btn)

        return self

    def savePreferences_(self, sender):
        ws = os.path.expanduser("~/.susops")
        os.makedirs(ws, exist_ok=True)
        # write prefs with newline
        for name, field in (("ssh_host", self.ssh_field),
                            ("socks_port", self.socks_field),
                            ("pac_port", self.pac_field)):
            val = str(field.stringValue()) + "\n"
            with open(os.path.join(ws, name), "w") as f:
                f.write(val)

        restart = alert_foreground(
            "Preferences Saved",
            "Settings will be applied on next start.\n\nRestart now?",
            ok="Yes", cancel="No"
        )

        if restart == 1:
            self.parent_app.restart_proxy(None)
        self.close()

    def cancelPreferences_(self, sender):
        self.close()

    def run(self):
        self.center()
        self.makeKeyAndOrderFront_(None)


class SusOpsApp(rumps.App):
    def __init__(self, icon_dir=None):
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.images_dir = icon_dir or os.path.join(self.base_dir, 'images')
        self.process_state = ProcessState.STOPPED

        # Initialize with no title so only icon is shown
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

        self._prefs_panel = None
        self.local_panel = None
        self.remote_panel = None

        self.menu = [
            rumps.MenuItem("Start Proxy", callback=self.start_proxy),
            rumps.MenuItem("Stop Proxy", callback=self.stop_proxy),
            rumps.MenuItem("Restart Proxy", callback=self.restart_proxy),
            None,
            rumps.MenuItem("Status", callback=self.check_status_item),
            rumps.MenuItem("List All", callback=self.list_hosts),
            None,
            rumps.MenuItem("Add Host…", callback=self.add_host),
            rumps.MenuItem("Add Local Forward…", callback=self.open_local_forward),
            rumps.MenuItem("Add Remote Forward…", callback=self.open_remote_forward),
            rumps.MenuItem("Remove Any…", callback=self.remove_any),
            None,
            rumps.MenuItem("Test Any…", callback=self.test_host),
            rumps.MenuItem("Test All", callback=self.test_all),
            None,
            rumps.MenuItem("Preferences…", callback=self.open_preferences),
            None,
            rumps.MenuItem("Quit", callback=self.quit_app)
        ]

        self._check_timer = rumps.Timer(self.check_status, 5)
        self._check_timer.start()

    def check_status(self, _=None):
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

        if new_state != self.process_state:
            self.process_state = new_state
            self.update_icon()

    def appearanceChanged_(self, note):
        # Called when user switches between light/dark mode
        self.update_icon()

    def update_icon(self):
        # choose file based on state and appearance
        app = NSApplication.sharedApplication()
        appearance = app.effectiveAppearance().name()
        theme = 'light' if 'Dark' in appearance else 'dark'
        fname = f"logo_{theme}_{self.process_state.value}.svg"
        path = os.path.join(self.images_dir, fname)
        self.icon = path

    @staticmethod
    def _run_susops(command, show_alert=True):
        print(f"Running command: {script} {command}")
        result = subprocess.run(f"{script} {command}", shell=True, capture_output=True, encoding="utf-8",
                                errors="ignore")
        if result.returncode != 0 and show_alert:
            alert_foreground("Error", result.stdout.strip())
        return result.stdout.strip(), result.returncode

    @staticmethod
    def load_prefs():
        ws = os.path.expanduser("~/.susops")
        defaults = {"ssh_host": "pi", "socks_port": "1080", "pac_port": "1081"}
        prefs = {}
        for name in defaults:
            path = os.path.join(ws, name)
            try:
                with open(path) as f:
                    prefs[name] = f.read().strip()
            except IOError:
                prefs[name] = defaults[name]
        return prefs

    @rumps.clicked("Start Proxy")
    def start_proxy(self, _):
        """Start the proxy in a fully detached background session using setsid."""
        prefs = self.load_prefs()
        cmd = f"{script} start {prefs['ssh_host']} {prefs['socks_port']} {prefs['pac_port']}"
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
            self.check_status()
        except Exception as e:
            alert_foreground("Error starting proxy", str(e))

    @rumps.clicked("Stop Proxy")
    def stop_proxy(self, _):
        output, _ = self._run_susops("stop --keep-ports")
        self.check_status()

    @rumps.clicked("Restart Proxy")
    def restart_proxy(self, _):
        p = self.load_prefs()
        cmd = f"restart {p['ssh_host']} {p['socks_port']} {p['pac_port']}"
        output, _ = self._run_susops(cmd)
        self.check_status()

    @rumps.clicked("Status")
    def check_status_item(self, _):
        output, _ = self._run_susops("ps", False)
        alert_foreground("SusOps Status", output)

    @rumps.clicked("List All")
    def list_hosts(self, _):
        output, _ = self._run_susops("ls")
        alert_foreground("SusOps Hosts", output)

    @rumps.clicked("Add Host…")
    def add_host(self, _):
        host = rumps.Window("Enter hostname to add:", "SusOps: Add Host", dimensions=(220, 20)).run().text
        if host:
            output, _ = self._run_susops(f"add {host}")
            rumps.notification("SusOps", "Add Host", output)

    @rumps.clicked("Add Local Forward…")
    def open_local_forward(self, _):
        if not self.local_panel:
            frame = NSMakeRect(0, 0, 320, 150)
            style = (NSWindowStyleMaskTitled | NSWindowStyleMaskClosable | NSWindowStyleMaskResizable)
            self.local_panel = LocalForwardPanel.alloc().initWithContentRect_styleMask_backing_defer_(
                frame, style, NSBackingStoreBuffered, False
            )
            self.local_panel.setTitle_("Add Local Forward")
            self.local_panel.parent_app = self

        self.local_panel.configure_fields([
            ('local_port_field', 'From Local Port:'),
            ('remote_port_field', 'To Remote Port:'),
        ])
        self.local_panel.run()

    def open_remote_forward(self, _):
        if not self.remote_panel:
            frame = NSMakeRect(0, 0, 320, 150)
            style = (NSWindowStyleMaskTitled | NSWindowStyleMaskClosable | NSWindowStyleMaskResizable)
            self.remote_panel = RemoteForwardPanel.alloc().initWithContentRect_styleMask_backing_defer_(
                frame, style, NSBackingStoreBuffered, False
            )
            self.remote_panel.setTitle_("Add Remote Forward")
            self.remote_panel.parent_app = self

        self.remote_panel.configure_fields([
            ('remote_port_field', 'From Remote Port:'),
            ('local_port_field', 'To Local Port:'),
        ])
        self.remote_panel.run()

    @rumps.clicked("Remove Any…")
    def remove_any(self, _):
        host = rumps.Window("Enter hostname or port to remove:", "SusOps: Remove Any", dimensions=(220, 20)).run().text
        if host:
            output, _ = self._run_susops(f"rm {host}")
            rumps.notification("SusOps", "Remove Any", output)

    @rumps.clicked("Test Any…")
    def test_host(self, _):
        host = rumps.Window("Enter hostname or port to test: ", "SusOps: Test Any", dimensions=(220, 20)).run().text
        if host:
            output, _ = self._run_susops(f"test {host}", False)
            alert_foreground("SusOps Test", output)

    @rumps.clicked("Test All")
    def test_all(self, _):
        output, _ = self._run_susops("test --all", False)
        alert_foreground("SusOps Test All", output)

    @rumps.clicked("Preferences…")
    def open_preferences(self, _):
        NSApplication.sharedApplication().activateIgnoringOtherApps_(True)
        if self._prefs_panel is None:
            frame = NSMakeRect(0, 0, 310, 190)
            style = (
                    NSWindowStyleMaskTitled
                    | NSWindowStyleMaskClosable
                    | NSWindowStyleMaskResizable
            )
            self._prefs_panel = PrefsPanel.alloc().initWithContentRect_styleMask_backing_defer_(
                frame, style, NSBackingStoreBuffered, False
            )
            self._prefs_panel.parent_app = self
        prefs = self.load_prefs()
        self._prefs_panel.ssh_field.setStringValue_(prefs['ssh_host'])
        self._prefs_panel.socks_field.setStringValue_(prefs['socks_port'])
        self._prefs_panel.pac_field.setStringValue_(prefs['pac_port'])
        self._prefs_panel.run()

    @rumps.clicked("Quit")
    def quit_app(self, _):
        self._run_susops("stop --keep-ports", False)
        rumps.quit_application()


if __name__ == "__main__":
    SusOpsApp().run()
