# Copyright (c) 2020 Fistro Co.

from ovs import ovsuuid
import tkinter
from tkinter import font
from tkinter import ttk

from ovn_viewer import constants
from ovn_viewer import treetypes


class OvnViewer(tkinter.Frame):

    def __init__(self, master_window, ovn_nb, ovn_sb):
        super(OvnViewer, self).__init__(master=master_window)
        self._ovn_nb = ovn_nb
        self._ovn_sb = ovn_sb
        self.root_tree = None
        self._configure_monspace_font()
        self._init_ui()

    def _configure_monspace_font(self):
        for font_family in (ff for ff in font.families()
                            if ff in constants.MONOSPACE_FONTS):
            self._font = font.Font(family=font_family, size=10, weight=font.NORMAL)
            return
        self._font = font.Font(size=10, weight=font.NORMAL)

    def _add_menu(self):
        menubar = tkinter.Menu(master=self.master)
        self.master.config(menu=menubar)

        file_menu = tkinter.Menu(master=menubar)
        file_menu.add_command(label='Exit', command=self._menu_exit)
        menubar.add_cascade(label='File', menu=file_menu)

        refresh_menu = tkinter.Menu(master=menubar)
        refresh_menu.add_command(label='Force single refresh',
                                 command=self._menu_single_refresh)
        refresh_menu.add_separator()
        refresh_menu.add_command(label='Enable auto-refresh',
                                 command=self._menu_enable_refresh)
        refresh_menu.add_command(label='Disable auto-refresh',
                                 command=self._menu_disable_refresh)
        menubar.add_cascade(label='IDL events', menu=refresh_menu)

    def _init_ui(self):
        self._add_menu()

        master_frame = tkinter.Frame(master=self.master)
        master_frame.grid(row=1, column=0, columnspan=5, padx=0, pady=0,
                          sticky=tkinter.E + tkinter.W + tkinter.N + tkinter.S)
        master_frame.rowconfigure(0, weight=1)
        master_frame.columnconfigure(0, weight=1)
        master_frame.pack(expand=True, fill='both')

        #######################################################################
        style = ttk.Style()
        style.configure('Treeview', font=self._font)
        self.treeview = ttk.Treeview(master_frame)
        #self.treeview.option_add("*font", self._font)
        self.treeview.pack(expand=True, fill='both')

        # Bottom text box.
        self.text_box = tkinter.StringVar()
        label = tkinter.Label(master_frame, textvariable=self.text_box,
                              height=6, justify=tkinter.LEFT,
                              font=self._font)
        label.pack(side='left')
        self.text_box.set('(no item selected)')
        self.treeview.bind('<<TreeviewSelect>>', self._event_select)

        self.root_tree = treetypes.RootTree(self.treeview, self._ovn_nb,
                                            self._ovn_sb)
        self.root_tree.populate_subtree()

    def _menu_exit(self):
        self.quit()

    def _menu_single_refresh(self):
        # TODO(ralonsoh): force one single refresh.
        pass

    def _menu_enable_refresh(self):
        # TODO(ralonsoh): enable auto refresh, see OvnIdl.notify
        pass

    def _menu_disable_refresh(self):
        # TODO(ralonsoh): enable auto refresh, see OvnIdl.notify
        pass

    def _event_select(self, event):
        selected = event.widget.selection()
        tree_item = self.treeview.item(selected)
        if not tree_item['tags']:
            return
        uuid = tree_item['values'][0]
        ovn_item_type = tree_item['tags'][0]
        self.root_tree.print_on_text_box(self.text_box, ovn_item_type, uuid)
