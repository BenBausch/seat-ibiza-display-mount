"""Open the generated holder in the FreeCAD GUI with colours.

Run from FreeCAD (Macro > Macros... > Execute) or:
  open -a FreeCAD --args "$PWD/show_in_freecad.py"
Regenerate first with ibiza_screen_holder.py if you changed params.json.
The colours are saved into out/ibiza_screen_holder.FCStd, so afterwards a plain
double-click on that file shows them too (until the next regeneration).
"""
import os
import sys
import FreeCAD as App
import FreeCADGui as Gui


def _project_dir():
    """Folder of this macro: __file__ if FreeCAD sets it, else the command-line argument, else cwd."""
    cands = []
    if "__file__" in globals():
        cands.append(os.path.dirname(os.path.abspath(__file__)))
    cands += [os.path.dirname(os.path.abspath(a)) for a in sys.argv if a.endswith("show_in_freecad.py")]
    cands.append(os.getcwd())
    for c in cands:
        if os.path.exists(os.path.join(c, "out", "ibiza_screen_holder.FCStd")):
            return c
    raise RuntimeError("out/ibiza_screen_holder.FCStd not found - run ibiza_screen_holder.py first")


HERE = _project_dir()
PATH = os.path.join(HERE, "out", "ibiza_screen_holder.FCStd")

STYLE = {                     # colour (r, g, b), transparency %
    "Body": ((0.22, 0.47, 0.82), 0),
    "Lid": ((0.55, 0.38, 0.80), 0),
    "Plug_L": ((0.96, 0.58, 0.12), 0),
    "Plug_R": ((0.96, 0.58, 0.12), 0),
    "Clamp_L": ((0.18, 0.72, 0.38), 0),
    "Clamp_R": ((0.18, 0.72, 0.38), 0),
    "Dummy_screen": ((0.13, 0.13, 0.15), 55),
    "Dummy_glass": ((0.22, 0.30, 0.44), 55),
    "Dummy_housings": ((0.80, 0.80, 0.82), 0),
    "Dummy_dash": ((0.66, 0.66, 0.68), 70),
    "Dummy_media": ((0.30, 0.30, 0.33), 30),
}


def show():
    for d in list(App.listDocuments().values()):
        if os.path.abspath(d.FileName) == os.path.abspath(PATH):
            App.closeDocument(d.Name)
    doc = App.openDocument(PATH)
    Gui.activateWorkbench("PartWorkbench")
    for o in doc.Objects:
        vo = o.ViewObject
        if vo is None or o.Name not in STYLE:
            continue
        rgb, tr = STYLE[o.Name]
        vo.ShapeColor = rgb
        vo.Transparency = tr
    grp = doc.getObject("Stand_ins") or doc.addObject("App::DocumentObjectGroup", "Stand_ins")
    for o in doc.Objects:
        if o.Name.startswith("Dummy_") and o not in grp.Group:
            grp.addObject(o)
    doc.recompute()
    Gui.ActiveDocument = Gui.getDocument(doc.Name)
    view = Gui.ActiveDocument.ActiveView
    view.viewIsometric()
    view.fitAll()
    try:
        doc.save()
    except Exception as e:  # read-only etc. - colours just aren't persisted
        App.Console.PrintWarning("could not save colours: %s\n" % e)
    App.Console.PrintMessage(
        "Holder loaded as installed: Z = up (level ground), -Y = towards the cabin. Front view (key 1) = "
        "from the seats, Right view (key 3) = side view with the real angles. Hide group 'Stand_ins' to see "
        "only the printed parts.\n")


try:
    from PySide import QtCore
    QtCore.QTimer.singleShot(800, show)      # let the main window finish starting up
except Exception:
    show()
