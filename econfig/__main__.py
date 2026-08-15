from __future__ import annotations

import argparse
import os

from .api import EConfigApplication, create_server
from .ibm_gateway import HttpEConfigGateway
from .service import ConfigurationService


def main() -> None:
    parser = argparse.ArgumentParser(description="Quick requirements to IBM eConfig CFR service")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()

    gateway = None
    if os.environ.get("IBM_ECONFIG_JWT"):
        gateway = HttpEConfigGateway.from_environment()
    application = EConfigApplication(ConfigurationService(gateway))
    server = create_server(args.host, args.port, application)
    print(f"econfig quick configurator listening on http://{args.host}:{args.port}")
    print(f"IBM gateway configured: {gateway is not None}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
