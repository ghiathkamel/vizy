#
# This file is part of Vizy 
#
# All Vizy source code is provided under the terms of the
# GNU General Public License v2 (http://www.gnu.org/licenses/gpl-2.0.html).
# Those wishing to use Vizy source code, software and/or
# technologies under different licensing terms should contact us at
# support@charmedlabs.com. 
#

import os 
import dash_html_components as html
from kritter import Kritter, Ktext, Kbutton, Kdialog, KsideMenuItem
from dash_devices.dependencies import Output

class AboutDialog:

    def __init__(self, kapp, pmask, pmask_edit):
        self.kapp = kapp
        # pmask isn't used because everyone can view about dialog.
        
        style = {"label_width": 3, "control_width": 8}
        self.img = html.Img(id=self.kapp.new_id(), style={"display": "block", "max-width": "100%", "margin-left": "auto", "margin-right": "auto"})
        self.version = Ktext(name="Version", style=style)
        self.loc = Ktext(name="Location", style=style)
        self.author = Ktext(name="Author", style=style)
        self.desc = Ktext(name="Description", style=style)
        self.info_button = Kbutton(name=[Kritter.icon("info-circle"), "More info"], target="_blank")
        self.view_edit_button = Kbutton(name=[Kritter.icon("edit"), "View/edit"], external_link=True, target="_blank")
        self.info_button.append(self.view_edit_button)
        layout = [self.img, self.version, self.author, self.loc, self.desc]
        self.dialog = Kdialog(title="", layout=layout, left_footer=self.info_button)
        self.layout = KsideMenuItem("", self.dialog, "info-circle")

        @self.kapp.callback_connect
        def func(client, connect):
            if connect:
                # Being able to view/edit source is privileged. 
                return self.view_edit_button.out_disp(client.authentication&pmask_edit)

    def out_update(self, prog):
        mods = []
        title = f"About {prog['name']}"
        if prog['version']:
            version = f"{prog['version']}, installed or modified on {prog['mrfd']}"
        else:
            version = f"installed or modified on {prog['mrfd']}"

        email = html.A(prog['email'], href=f"mailto:{prog['email']}") if prog["email"] else None
        if prog["author"]:
            if email:
                author = [prog["author"] + ", ", email]
            else:
                author = prog["author"]
        elif email:
            author = email
        else:
            author = None

        mods += self.loc.out_value(os.path.join(self.kapp.homedir, prog['path']))
        mods += self.info_button.out_disp(bool(prog['url']))
        if prog['url']:
            mods += self.info_button.out_url(prog['url'])

        mods += self.author.out_disp(bool(author))
        if author:
            mods += self.author.out_value(author)

        mods += self.desc.out_disp(bool(prog['description']))
        if prog['description']:
            mods += self.desc.out_value(prog['description'])
        
        return mods + self.layout.out_name(title) + self.dialog.out_title([Kritter.icon("info-circle"), title]) + [Output(self.img.id, "src", prog['image_no_bg'])] + self.version.out_value(version) 