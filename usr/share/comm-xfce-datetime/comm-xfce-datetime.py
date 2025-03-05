import gi
import os
import subprocess
import gettext
import datetime
import pytz
import threading

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GLib, Gdk, Gio


# Style Buttons
css_provider = Gtk.CssProvider()
css_provider.load_from_string(
    ".blue{background:#3584e4;}"
    ".red{background:#e43e35;}"
)
Gtk.StyleContext.add_provider_for_display(
    Gdk.Display.get_default(),
    css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
)

# Translation support
APP_NAME = "comm-xfce-datetime"
LOCALE_DIR = "/usr/share/locale"
gettext.bindtextdomain(APP_NAME, LOCALE_DIR)
gettext.textdomain(APP_NAME)
_ = gettext.gettext


class DateTimeApp(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app)
        self.set_title(_("Date and Time Settings"))
        self.set_default_size(500, 400)
        self.search_query = ""

        # Main layout
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        vbox.set_margin_start(10)
        vbox.set_margin_end(10)
        vbox.set_margin_top(10)
        vbox.set_margin_bottom(10)
        self.set_child(vbox)

        # Date group
        frame_date = Gtk.Frame(label=_("Select Date"))
        frame_date.set_label_align(0.5)
        date_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        date_box.set_margin_start(10)
        date_box.set_margin_end(10)
        date_box.set_margin_top(10)
        date_box.set_margin_bottom(10)
        self.calendar = Gtk.Calendar()
        date_box.append(self.calendar)
        frame_date.set_child(date_box)
        vbox.append(frame_date)

        # Time group
        frame_time = Gtk.Frame(label=_("Adjust Time"))
        frame_time.set_label_align(0.5)
        time_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        time_box.set_halign(Gtk.Align(3))
        time_box.set_margin_start(10)
        time_box.set_margin_end(10)
        time_box.set_margin_top(10)
        time_box.set_margin_bottom(10)
        self.hour_spinner = Gtk.SpinButton.new_with_range(0, 23, 1)
        self.minute_spinner = Gtk.SpinButton.new_with_range(0, 59, 1)
        self.set_initial_time()
        time_box.append(Gtk.Label(label=_("Hour:")))
        time_box.append(self.hour_spinner)
        time_box.append(Gtk.Label(label=_("Minute:")))
        time_box.append(self.minute_spinner)
        frame_time.set_child(time_box)
        vbox.append(frame_time)

        # Timezone group
        frame_timezone = Gtk.Frame(label=_("Select Timezone"))
        frame_timezone.set_label_align(0.5)
        frame_timezone.set_child(self.create_filtered_timezone_dropdown())
        vbox.append(frame_timezone)

        # Create option to enable/disable automatic synchronization
        self.ntp_checkbox = Gtk.CheckButton(
            label=_("Enable Automatic Synchronization")
        )
        # Initial state
        self.ntp_checkbox.set_active(self.is_ntp_enabled())
        self.ntp_toggle_lock = False
        self.ntp_checkbox.connect("toggled", self.on_ntp_toggled)
        vbox.append(self.ntp_checkbox)

        self.sync_label = Gtk.Label(label="")
        self.sync_label.set_visible(True)
        vbox.append(self.sync_label)

        # Buttons
        hbox_buttons = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=10
        )
        hbox_buttons.set_halign(Gtk.Align(3))
        save_button = Gtk.Button(label=_("Apply"))
        save_button.set_css_classes(['blue'])
        save_button.connect("clicked", self.on_save_clicked)
        cancel_button = Gtk.Button(label=_("Cancel"))
        cancel_button.set_css_classes(['red'])
        cancel_button.connect("clicked", self.on_cancel_clicked)
        sync_button = Gtk.Button(label=_("Synchronize"))
        sync_button.connect("clicked", self.on_sync_clicked)
        hbox_buttons.append(cancel_button)
        hbox_buttons.append(sync_button)
        hbox_buttons.append(save_button)
        vbox.append(hbox_buttons)

    def is_ntp_enabled(self):
        """Check if automatic synchronization service is active."""
        try:
            result = subprocess.run(
                ["timedatectl", "show", "--property=NTP"],
                capture_output=True, text=True, check=True
            )
            return "NTP=yes" in result.stdout
        except subprocess.CalledProcessError:
            return False

    def on_ntp_toggled(self, button):
        """Enable or disable automatic synchronization"""
        if self.ntp_toggle_lock:  # Avoid loop
            return

        self.ntp_toggle_lock = True

        new_state = "true" if button.get_active() else "false"
        if new_state == "true":
            msg = _("Auto synchronization enabled.")
        else:
            msg = _("Auto synchronization disabled.")

        try:
            self.run_command(["pkexec", "timedatectl", "set-ntp", new_state])
            GLib.idle_add(
                self.show_message_dialog,
                Gtk.MessageType.INFO,
                msg
            )
        except Exception as e:
            GLib.idle_add(
                self.show_message_dialog,
                Gtk.MessageType.ERROR,
                str(e)
            )
            button.set_active(not button.get_active())
        finally:
            self.ntp_toggle_lock = False

    def set_initial_time(self):
        """Set initial time based on the system's current time."""
        now = datetime.datetime.now()
        self.hour_spinner.set_value(now.hour)
        self.minute_spinner.set_value(now.minute)

    def create_filtered_timezone_dropdown(self):
        """Create a timezone dropdown with filter."""
        # Base model for timezones
        self.timezone_model = Gio.ListStore.new(Gtk.StringObject)
        for tz in pytz.all_timezones:
            item = Gtk.StringObject.new(tz)
            self.timezone_model.append(item)

        # Filter
        self.filter = Gtk.CustomFilter.new(self.filter_timezones, None)
        self.filter_model = Gtk.FilterListModel.new(self.timezone_model, self.filter)
        self.filter_model.set_filter(self.filter)

        # Dropdown
        self.timezone_dropdown = Gtk.DropDown(model=self.filter_model)
        self.timezone_dropdown.set_hexpand(True)

        # Search field
        self.search_entry = Gtk.Entry(placeholder_text=_("Search..."))
        self.search_entry.set_width_chars(15)
        self.search_entry.connect("changed", self.on_search_entry_changed)

        # Container
        timezone_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=10
        )
        timezone_box.set_hexpand(True)
        timezone_box.set_margin_start(10)
        timezone_box.set_margin_end(10)
        timezone_box.set_margin_top(10)
        timezone_box.set_margin_bottom(10)
        timezone_box.append(self.search_entry)
        timezone_box.append(self.timezone_dropdown)

        return timezone_box

    def filter_timezones(self, item, _):
        """Custom filter to search timezones."""
        query = self.search_query.lower()
        timezone_str = item.get_string().lower()
        return str(query) in timezone_str

    def on_search_entry_changed(self, entry):
        """Update filter when search text changes."""
        self.search_query = entry.get_text().strip()
        if self.filter:
            self.filter.changed(Gtk.FilterChange.DIFFERENT)

    def on_save_clicked(self, button):
        """Confirmation before applying settings."""
        try:
            # Get selected values
            day = self.calendar.props.day
            month = self.calendar.props.month + 1  # Month starts at 0
            year = self.calendar.props.year
            hour = self.hour_spinner.get_value_as_int()
            minute = self.minute_spinner.get_value_as_int()
            active_item = self.timezone_dropdown.get_selected_item()
            timezone = active_item.get_string() if active_item else None

            if not timezone:
                raise ValueError(_("No timezone selected."))

            date_str = f"{year}-{month:02}-{day:02}"
            time_str = f"{hour:02}:{minute:02}:00"
            date_str_inverted = f"{day:02}-{month:02}-{year}"

            # Confirmation message
            confirm_msg = _(
                "The following settings will be applied:\n\n"
                "Date: {}\n"
                "Time: {}\n"
                "Timezone: {}\n\n"
                "Do you want to continue?"
            ).format(date_str_inverted, time_str, timezone)

            # Create dialog
            dialog = Gtk.MessageDialog(
                transient_for=self,
                modal=True,
                message_type=Gtk.MessageType.QUESTION,
                buttons=Gtk.ButtonsType.YES_NO,
                text=confirm_msg
            )

            # Connect signal to capture user response
            dialog.connect(
                "response", self.on_confirm_response,
                date_str, time_str, timezone
            )
            dialog.present()

        except Exception as e:
            self.show_message_dialog(Gtk.MessageType.ERROR, str(e))

    def on_confirm_response(
        self, dialog, response,
        date_str, time_str, timezone
    ):
        """Apply settings if user confirms in the dialog."""
        if response == Gtk.ResponseType.DELETE_EVENT:
            return

        dialog.close()
        if response == Gtk.ResponseType.YES:
            try:
                self.run_command(["timedatectl", "set-timezone", timezone])
                self.run_command([
                    "timedatectl", "set-time",
                    f"{date_str} {time_str}"
                ])
                self.show_message_dialog(
                    Gtk.MessageType.INFO,
                    _("Settings applied successfully!")
                )
            except Exception as e:
                self.show_message_dialog(Gtk.MessageType.ERROR, str(e))

    def on_cancel_clicked(self, button):
        """Close the application without making any changes."""
        self.get_application().quit()

    def on_sync_clicked(self, button):
        """Synchronize with the Internet using ntpd and display a message."""
        button.set_sensitive(False)  # Disable button during synchronization
        self.sync_label.set_markup(
            "<i>" + _("Please wait, synchronizing...") + "</i>"
        )

        def sync_thread():
            try:
                process = subprocess.run(
                    ["pkexec", "ntpd", "-gq"],
                    capture_output=True,
                    text=True,
                    check=True
                )
                if process.returncode == 0:
                    GLib.idle_add(
                        self.show_message_dialog,
                        Gtk.MessageType.INFO,
                        _("Synchronization completed successfully!")
                    )
            except Exception as e:
                GLib.idle_add(
                    self.show_message_dialog,
                    Gtk.MessageType.ERROR,
                    str(e)
                )
            finally:
                GLib.idle_add(lambda: button.set_sensitive(True))
                GLib.idle_add(self.sync_label.set_text, "")

        threading.Thread(target=sync_thread, daemon=True).start()

    def run_command(self, command):
        """Run a command in the shell"""
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip())

    def show_message_dialog(self, message_type, message):
        """Display a dialog with a message."""
        dialog = Gtk.MessageDialog(
            transient_for=self,
            modal=True,
            message_type=message_type,
            buttons=Gtk.ButtonsType.OK,
            text=message,
        )
        dialog.connect("response", lambda d, r: d.close())
        dialog.present()


class DateTimeAppGtk(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="community.xfce.datetime")

    def do_activate(self):
        window = DateTimeApp(self)
        window.present()


if __name__ == "__main__":
    app = DateTimeAppGtk()
    app.run()
