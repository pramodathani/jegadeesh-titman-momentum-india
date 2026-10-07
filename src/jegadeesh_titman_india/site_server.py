"""Serves the bundled web app on this computer and opens it in a browser.

The app is a static site shipped inside the package, with the study's results as data files, so it needs no NSE downloads and no configuration. Browsers refuse to load a page's data files straight from disk, which is why a small local web server is used rather than opening `index.html` directly.

Typical usage example, after `pip install` of this repository:

  jt-momentum-app
  jt-momentum-app --port 8123 --no-browser
"""

import argparse
import functools
import http.server
import pathlib
import socket
import webbrowser


SITE_DIRECTORY = pathlib.Path(__file__).resolve().parent / 'site'

DEFAULT_PORT = 8000


class QuietRequestHandler(http.server.SimpleHTTPRequestHandler):
    """A static file handler that does not print a line for every request."""

    def log_message(self, format: str, *args) -> None:
        """Discards the per-request log line.

        Args:
            format: The str format of the message.
            *args: The values for the format.

        Returns:
            None.

        Raises:
            Nothing.
        """
        del format, args


class SiteServerApplication:
    """The command-line program that serves the web app locally."""

    @staticmethod
    def launch() -> None:
        """Runs the application; this is the target of the `jt-momentum-app` command.

        Returns:
            None.

        Raises:
            OSError: No port could be opened.
        """
        SiteServerApplication().run()

    def run(self) -> None:
        """Reads the command line, starts the server and opens the browser until interrupted.

        Returns:
            None.

        Raises:
            OSError: No port could be opened.
            FileNotFoundError: The site files are missing from the installed package.
        """
        parser = argparse.ArgumentParser(description='Serve the momentum study web app on this computer.')
        parser.add_argument('--port', type=int, default=DEFAULT_PORT)
        parser.add_argument('--no-browser', action='store_true')
        arguments = parser.parse_args()
        if not (SITE_DIRECTORY / 'index.html').exists():
            raise FileNotFoundError(f'The web app is missing from the package: {SITE_DIRECTORY}')
        port = self.free_port(arguments.port)
        handler = functools.partial(QuietRequestHandler, directory=str(SITE_DIRECTORY))
        server = http.server.ThreadingHTTPServer(('127.0.0.1', port), handler)
        address = f'http://127.0.0.1:{port}/'
        print(f'Serving the momentum study at {address}  (press Ctrl+C to stop)')
        if not arguments.no_browser:
            webbrowser.open(address)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print('Stopped.')
        finally:
            server.server_close()

    def free_port(self, preferred: int) -> int:
        """Finds a port to listen on, trying the preferred one and the next nineteen.

        Args:
            preferred: The int port to try first.

        Returns:
            The int first port that is free.

        Raises:
            OSError: None of the twenty ports is free.
        """
        for port in range(preferred, preferred + 20):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
                if probe.connect_ex(('127.0.0.1', port)) != 0:
                    return port
        raise OSError(f'No free port between {preferred} and {preferred + 19}')


if __name__ == '__main__':
    SiteServerApplication().run()
