# Copyright (c) 2020 Fistro Co.

from ovs import ovsuuid
from ovsdbapp.backend.ovs_idl import idlutils
from ovsdbapp.backend.ovs_idl import connection
from ovsdbapp.schema.ovn_northbound import impl_idl as nb_impl_idl
import tkinter
from tkinter import ttk

from ovn_viewer import connection
from ovn_viewer import constants
from ovn_viewer import treetypes


###############################################################################
class OvnViewer(tkinter.Frame):

    def __init__(self, master_window, ovn_nb, ovn_sb):
        super(OvnViewer, self).__init__(master=master_window)
        self._ovn_nb = ovn_nb
        self._ovn_sb = ovn_sb
        self._init_ui()

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

        frame = tkinter.Frame(master=self.master)
        #frame.pack(fill=BOTH, expand=1)
        #frame.pack()

        master_frame = tkinter.Frame(master=self.master)
        master_frame.grid(row=1, column=0, columnspan=5, padx=0, pady=0,
                          sticky=tkinter.E + tkinter.W + tkinter.N + tkinter.S)
        master_frame.rowconfigure(0, weight=1)
        master_frame.columnconfigure(0, weight=1)
        master_frame.pack(expand=True, fill='both')

        ###############################################################################
        # Creating treeview window
        self.treeview = ttk.Treeview(master_frame)
        # # Calling pack method on the treeview
        self.treeview.pack(expand=True, fill='both')

        ###############################################################################
        # Create text box
        self.text_box = tkinter.StringVar()
        label = tkinter.Label(master_frame, textvariable=self.text_box,
                              height=6, justify=tkinter.LEFT)
        label.pack(side='left')
        self.text_box.set('(no item selected)')
        self.treeview.bind('<<TreeviewSelect>>', self._event_select)

        # LOGICAL_WITCH
        ls_tt = treetypes.LogicalSwitches(self.treeview, self._ovn_nb,
                                          self._ovn_sb)
        ls_tt.populate_subtree()


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
        uuid = ovsuuid.from_string(tree_item['values'][0])
        ovs_item_type = tree_item['tags'][0]
        ovs_item = self._ovn_nb.tables[ovs_item_type].rows.get(uuid)
        self.print_on_text_box(self.text_box, ovs_item._data, ovs_item_type)

    def print_on_text_box(self, text_box, datum, type):
        # TODO(ralonsoh): this is an abomination. Let each element to print
        #                 its own data into the text box.
        if type == constants.LOGICAL_SWITCH:
            text_box.set('name: %(name)s\n'
                         'other_config: %(other_config)s\n'
                         'external_ids: %(external_ids)s' %
                         {'name': datum['name'],
                          'other_config': datum['other_config'],
                          'external_ids': datum['external_ids'],
                          })

        elif type == constants.LOGICAL_SWITCH_PORT:
            text_box.set(
                'id: %(id)s  --  name: %(name)s\n'
                'device_id: %(device_id)s\n'
                'addresses: %(addresses)s  -- cidrs: %(cidrs)s\n'
                'ha_chassis_group: %(ha_chassis_group)s\n'
                'type: %(type)s\n' %
                {'id': datum['name'],
                 'device_id': datum['external_ids'].get('neutron:device_id'),
                 'name': datum['external_ids'].get('neutron:port_name'),
                 'addresses': datum['addresses'],
                 'cidrs': datum['external_ids'].get('neutron:cidrs'),
                 'ha_chassis_group': datum['ha_chassis_group'],
                 'type': datum['type'],
                 })






