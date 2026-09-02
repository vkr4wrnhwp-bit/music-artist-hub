"""The rendered stage plot, kept so an advance email can attach it.

The plot is drawn in the browser (static/js/stageplot.js) and this server
has no renderer, so the page rasterises its own SVG and posts the PNG
here. One image per artist, replaced on every save - the plot is one per
artist too. Stored in the bucket under plots/ when the bucket accepts
writes, otherwise in a private directory beside the database; never the
public uploads tree.
"""
import os

import blob_store

PREFIX = "plot:"
MAX_BYTES = 4 * 1024 * 1024


def _dir():
    import db
    path = os.path.join(os.path.dirname(db.db_path()), "stage_plot_images")
    os.makedirs(path, exist_ok=True)
    return path


def save(user_id, data):
    """Keep these bytes as the artist's current plot image. Returns the
    stored path, which the row records."""
    import db
    fname = "%s.png" % user_id
    path = None
    if blob_store.configured():
        try:
            if blob_store.put("plots/" + fname, data, "image/png"):
                path = blob_store.PREFIX + "plots/" + fname
        except Exception:
            path = None
    if path is None:
        with open(os.path.join(_dir(), fname), "wb") as fh:
            fh.write(data)
        path = PREFIX + fname
    db.save_stage_plot_image(user_id, path)
    return path


def read(user_id):
    """The bytes, or None when nothing was saved or it is gone."""
    import db
    rec = db.get_stage_plot_image(user_id)
    if not rec:
        return None
    path = rec["path"]
    if blob_store.is_remote(path):
        return blob_store.fetch(path)
    if path.startswith(PREFIX):
        try:
            with open(os.path.join(_dir(), path[len(PREFIX):]), "rb") as fh:
                return fh.read()
        except OSError:
            return None
    return None
