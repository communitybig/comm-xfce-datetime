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

# Suporte a tradução
APP_NAME = "datetime_tool"
LOCALE_DIR = os.path.join(os.path.dirname(__file__), "locales")
gettext.bindtextdomain(APP_NAME, LOCALE_DIR)
gettext.textdomain(APP_NAME)
_ = gettext.gettext


class DateTimeApp(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app)
        self.set_title(_("Configurações de Data e Hora"))
        self.set_default_size(500, 400)

        # Layout principal
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        vbox.set_margin_start(10)
        vbox.set_margin_end(10)
        vbox.set_margin_top(10)
        vbox.set_margin_bottom(10)
        self.set_child(vbox)

        # Grupo de data
        frame_date = Gtk.Frame(label=_("Selecione a data"))
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

        # Grupo de hora
        frame_time = Gtk.Frame(label=_("Ajuste o horário"))
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
        time_box.append(Gtk.Label(label=_("Hora:")))
        time_box.append(self.hour_spinner)
        time_box.append(Gtk.Label(label=_("Minuto:")))
        time_box.append(self.minute_spinner)
        frame_time.set_child(time_box)
        vbox.append(frame_time)

        # Grupo de fuso horário
        frame_timezone = Gtk.Frame(label=_("Selecione o fuso horário"))
        frame_timezone.set_label_align(0.5)
        self.search_query = ""
        frame_timezone.set_child(self.create_filtered_timezone_dropdown())
        vbox.append(frame_timezone)

        # Criando a opção de ativar/desativar a sincronização automática
        self.ntp_checkbox = Gtk.CheckButton(
            label=_("Ativar sincronização automática")
        )
        # Estado inicial
        self.ntp_checkbox.set_active(self.is_ntp_enabled())
        self.ntp_toggle_lock = False
        self.ntp_checkbox.connect("toggled", self.on_ntp_toggled)
        vbox.append(self.ntp_checkbox)

        self.sync_label = Gtk.Label(label="")
        self.sync_label.set_visible(True)
        vbox.append(self.sync_label)

        # Botões
        hbox_buttons = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=10
        )
        hbox_buttons.set_halign(Gtk.Align(3))
        save_button = Gtk.Button(label=_("Aplicar"))
        save_button.set_css_classes(['blue'])
        save_button.connect("clicked", self.on_save_clicked)
        cancel_button = Gtk.Button(label=_("Cancelar"))
        cancel_button.set_css_classes(['red'])
        cancel_button.connect("clicked", self.on_cancel_clicked)
        sync_button = Gtk.Button(label=_("Sincronizar"))
        sync_button.connect("clicked", self.on_sync_clicked)
        hbox_buttons.append(cancel_button)
        hbox_buttons.append(sync_button)
        hbox_buttons.append(save_button)
        vbox.append(hbox_buttons)

    def is_ntp_enabled(self):
        """Verifica se o serviço de sincronização automática está ativo."""
        try:
            result = subprocess.run(
                ["timedatectl", "show", "--property=NTP"],
                capture_output=True, text=True, check=True
            )
            return "NTP=yes" in result.stdout
        except subprocess.CalledProcessError:
            return False

    def on_ntp_toggled(self, button):
        """Ativa ou desativa a sincronização automática"""
        if self.ntp_toggle_lock:  # Evita loop
            return

        self.ntp_toggle_lock = True

        new_state = "true" if button.get_active() else "false"
        if new_state == "true":
            msg = _("Sincronização automática ativada.")
        else:
            msg = _("Sincronização automática desativada.")

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
        """Define a hora inicial com base no horário atual do sistema."""
        now = datetime.datetime.now()
        self.hour_spinner.set_value(now.hour)
        self.minute_spinner.set_value(now.minute)

    def create_filtered_timezone_dropdown(self):
        """Cria um dropdown de fusos horários com filtro."""
        # Modelo base para os fusos horários
        self.timezone_model = Gio.ListStore.new(Gtk.StringObject)
        for tz in pytz.all_timezones:
            self.timezone_model.append(Gtk.StringObject.new(tz))

        # Filtro
        self.filter = Gtk.CustomFilter.new(self.filter_timezones, None)
        self.filter_model = Gtk.FilterListModel.new(self.timezone_model, self.filter)
        self.filter_model.set_filter(self.filter)

        # Dropdown
        self.timezone_dropdown = Gtk.DropDown(model=self.filter_model)
        self.timezone_dropdown.set_hexpand(True)

        # Campo de busca
        self.search_entry = Gtk.Entry(placeholder_text=_("Pesquisar..."))
        self.search_entry.set_width_chars(15)
        self.search_entry.connect("changed", self.on_search_entry_changed)

        # Contêiner
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
        """Filtro personalizado para buscar fusos horários."""
        if not isinstance(item, Gtk.StringObject):
            return False

        query = self.search_query.lower()
        return query in item.get_string().lower()

    def on_search_entry_changed(self, entry):
        """Atualiza o filtro quando o texto de busca muda."""
        self.search_query = entry.get_text().strip()
        self.filter.changed(Gtk.FilterChange.DIFFERENT)

    def on_save_clicked(self, button):
        """Confirmação antes de aplicar as configurações."""
        try:
            # Obtém os valores selecionados
            day = self.calendar.props.day
            month = self.calendar.props.month + 1  # Mês começa em 0
            year = self.calendar.props.year
            hour = self.hour_spinner.get_value_as_int()
            minute = self.minute_spinner.get_value_as_int()
            active_item = self.timezone_dropdown.get_selected_item()
            timezone = active_item.get_string() if active_item else None

            if not timezone:
                raise ValueError(_("Nenhum fuso horário selecionado."))

            date_str = f"{year}-{month:02}-{day:02}"
            time_str = f"{hour:02}:{minute:02}:00"
            date_str_inverted = f"{day:02}-{month:02}-{year}"

            # Mensagem de confirmação
            confirm_msg = _(
                "As seguintes configurações serão aplicadas:\n\n"
                "Data: {}\n"
                "Hora: {}\n"
                "Fuso horário: {}\n\n"
                "Deseja continuar?"
            ).format(date_str_inverted, time_str, timezone)

            # Criando o diálogo
            dialog = Gtk.MessageDialog(
                transient_for=self,
                modal=True,
                message_type=Gtk.MessageType.QUESTION,
                buttons=Gtk.ButtonsType.YES_NO,
                text=confirm_msg
            )

            # Conectando o sinal para capturar a resposta do usuário
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
        """Executa as configurações se o usuário confirmar no diálogo."""
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
                    _("Configurações aplicadas com sucesso!")
                )
            except Exception as e:
                self.show_message_dialog(Gtk.MessageType.ERROR, str(e))

    def on_cancel_clicked(self, button):
        """Fecha o aplicativo sem alterar nada."""
        self.get_application().quit()

    def on_sync_clicked(self, button):
        """Sincroniza com a Internet utilizando ntpd e exibe uma mensagem."""
        button.set_sensitive(False)  # Desativa o botão durante a sincronização
        self.sync_label.set_markup(
            "<i>" + _("Aguarde, sincronizando...") + "</i>"
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
                        _("Sincronização concluída com sucesso!")
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
        """Executa um comando no shell"""
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip())

    def show_message_dialog(self, message_type, message):
        """Exibe uma caixa de diálogo com uma mensagem."""
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
