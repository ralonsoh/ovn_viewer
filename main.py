#!/usr/bin/python
#
# Copyright (c) 2020 Fistro Co.

from ovsdbapp.backend.ovs_idl import connection
import tkinter

from ovn_viewer import connection
from ovn_viewer import viewer


def main():
    master_window = tkinter.Tk()
    # Full SVGA resolution, welcome to the future
    master_window.minsize(800, 600)
    master_window.title('OVN tree viewer')
    ovn_nb, ovn_sb = connection.get_ovn_conn()
    viewer.OvnViewer(master_window, ovn_nb, ovn_sb)
    master_window.mainloop()


if __name__ == '__main__':
    main()
