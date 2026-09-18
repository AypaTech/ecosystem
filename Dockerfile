# AypaTech — Odoo 20 image (this repo's own ecosystem modules only,
# independent from FreelanceERP). Uses Debian bookworm (stable) rather than
# bleeding-edge Ubuntu, so package resolution stays predictable regardless
# of what the host OS is.
FROM python:3.12-slim-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
        git wget curl ca-certificates \
        build-essential libxml2-dev libxslt1-dev libldap2-dev libsasl2-dev \
        libssl-dev libjpeg-dev zlib1g-dev libpq-dev \
        libfreetype6-dev liblcms2-dev libopenjp2-7-dev libtiff-dev \
        tk-dev tcl-dev \
        fonts-dejavu-core fonts-freefont-ttf fonts-noto-cjk fontconfig xfonts-75dpi xfonts-base \
        nodejs npm \
        postgresql-client \
    && npm install -g rtlcss \
    && rm -rf /var/lib/apt/lists/*

# wkhtmltopdf — patched-Qt build required for PDF reports
RUN wget -q https://github.com/wkhtmltopdf/packaging/releases/download/0.12.6.1-3/wkhtmltox_0.12.6.1-3.bookworm_amd64.deb -O /tmp/wkhtmltox.deb \
    && apt-get update \
    && apt-get install -y --no-install-recommends /tmp/wkhtmltox.deb \
    && rm /tmp/wkhtmltox.deb \
    && rm -rf /var/lib/apt/lists/*

# Odoo 20.0 source
RUN git clone --depth 1 --branch 20.0 https://github.com/odoo/odoo.git /opt/odoo/odoo-server

# Python dependencies
RUN pip install --no-cache-dir -r /opt/odoo/odoo-server/requirements.txt

# This repo's own AypaTech ecosystem modules — copy the whole build context,
# then keep only the actual addon folders (anything with a __manifest__.py),
# so .git/.github/Dockerfile/etc. never end up on the addons path.
COPY . /tmp/ecosystem-src/
RUN mkdir -p /opt/odoo/custom-addons \
    && for d in /tmp/ecosystem-src/*/; do \
         if [ -f "$d/__manifest__.py" ]; then mv "$d" /opt/odoo/custom-addons/; fi; \
       done \
    && rm -rf /tmp/ecosystem-src

EXPOSE 8069
ENTRYPOINT ["python3", "/opt/odoo/odoo-server/odoo-bin"]
