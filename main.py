#!/usr/bin/python
#
# Copyright (c) 2020 Fistro Co.

import tkinter

from ovn_viewer import viewer


def main():
    master_window = tkinter.Tk()
    # Full SVGA resolution, welcome to the future
    master_window.minsize(800, 600)
    master_window.title('OVN tree viewer')
    _viewer = viewer.OvnViewer(master_window)
    _viewer.init_ui()
    master_window.mainloop()


if __name__ == '__main__':
    main()
