from fastapi.templating import Jinja2Templates

from app import __version__

# Shared by every router so all pages get the same globals (e.g. the version in the footer).
templates = Jinja2Templates(directory="app/templates")
templates.env.globals["app_version"] = __version__
