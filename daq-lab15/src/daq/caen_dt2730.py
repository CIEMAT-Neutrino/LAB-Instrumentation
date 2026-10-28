"""
@file caen_dt2730.py
@brief Remote control of the CAEN DT2730 digitizer through CoMPASS.

@details
CoMPASS (with DPP-PSD firmware) must be running on the PC connected to the
digitizer, with the board already added and the "Remote Control" button enabled
in the CoMPASSPlot window. CoMPASS then starts an HTTP server (port 8080 by
default) that only handles GET requests:

  - http://IP:8080/compass/START  -> start the acquisition
  - http://IP:8080/compass/STOP   -> stop the acquisition
  - http://IP:8080/compass?PARAMETER=value[&PARAMETER=value...]

Supported parameters: loadConfigFile, runId, autoIncrementRunId,
timedRunEnabled and timedRunDuration.

@note Do not load a configuration file and modify parameters in the same HTTP
request: the execution order is not guaranteed.
@note CoMPASS has no command to query whether an acquisition has finished; the
caller must wait the desired time and then send STOP.
@note A folder with the same runId must not already exist in the CoMPASS
project, otherwise the acquisition will not start.
"""

import time

import requests


class CompassError(Exception):
    """
    @brief Error while communicating with CoMPASS.
    @details Raised when the server cannot be reached or when it answers with an
    HTTP status code other than 200 (403, 404, 500, 501, 599...).
    """


class CaenDT2730:
    """
    @brief HTTP client for the CoMPASS remote control (DT2730 digitizer).
    """

    ## Text CoMPASS expects for a true boolean parameter.
    _TRUE = "TRUE"
    ## Text CoMPASS expects for a false boolean parameter.
    _FALSE = "FALSE"

    def __init__(self, host="127.0.0.1", port=8080, wait_time=6.0, timeout=10.0):
        """
        @brief Constructor. It does not open any persistent connection.
        @param host      IP address of the PC running CoMPASS ("127.0.0.1" if local).
        @param port      Port of the CoMPASS remote control server.
        @param wait_time Seconds to wait after commands that the server takes time
                         to process (config loading, parameters, STOP).
        @param timeout   Maximum time (s) to wait for the HTTP response.
        """
        self.base = f"http://{host}:{port}/compass"
        self.wait_time = wait_time
        self.timeout = timeout

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #
    def _get(self, path="", params=None):
        """
        @brief Send a GET request to the CoMPASS server.
        @param path   Path appended to the base URL (e.g. "/START").
        @param params Dictionary with the query string parameters.
        @return requests.Response object with the server response.
        @throws CompassError If the connection fails or the HTTP status is not 200.
        """
        url = self.base + path
        try:
            r = requests.get(url, params=params, timeout=self.timeout)
        except requests.RequestException as e:
            raise CompassError(f"Could not connect to CoMPASS ({url}): {e}") from e
        if r.status_code != 200:
            raise CompassError(f"CoMPASS returned {r.status_code} for {r.url}")
        return r

    def _settle(self):
        """
        @brief Wait wait_time seconds so the server can process the command.
        """
        time.sleep(self.wait_time)

    # ------------------------------------------------------------------ #
    # Commands
    # ------------------------------------------------------------------ #
    def test_connection(self):
        """
        @brief Check that the remote control server is responding.
        @return CoMPASS welcome message.
        @throws CompassError If the connection fails.
        """
        return self._get("/").text

    def load_config(self, filename):
        """
        @brief Load a CoMPASS configuration file.
        @param filename Name of the .xml file (e.g. "config1_thr_15LSB.xml"); it
                        must be in the CONFIG folder of the CoMPASS project.
        @throws CompassError If the server rejects the request.
        """
        self._get(params={"loadConfigFile": filename})
        self._settle()

    def set_parameters(self, **params):
        """
        @brief Set one or more acquisition parameters in a single request.
        @param params Parameter=value pairs. bool values are converted to TRUE/FALSE.
                      Example: set_parameters(runId="run_A", autoIncrementRunId=False)
        @throws CompassError If the server rejects the request.
        """
        conv = {
            k: (self._TRUE if v else self._FALSE) if isinstance(v, bool) else v
            for k, v in params.items()
        }
        self._get(params=conv)
        self._settle()

    def set_run_id(self, run_id, auto_increment=False):
        """
        @brief Set the run name and the runId auto-increment option.
        @param run_id         Run name (no spaces allowed).
        @param auto_increment If True, CoMPASS appends an index to each run.
        @throws CompassError If the server rejects the request.
        """
        self.set_parameters(runId=run_id, autoIncrementRunId=auto_increment)

    def start(self):
        """
        @brief Start the acquisition.
        @throws CompassError If the server rejects the request.
        """
        self._get("/START")

    def stop(self):
        """
        @brief Stop the acquisition and wait for the server to close the run.
        @throws CompassError If the server rejects the request.
        """
        self._get("/STOP")
        self._settle()

    def run(self, duration_s):
        """
        @brief Perform a complete acquisition: START, wait and STOP.
        @param duration_s Acquisition duration in seconds. The actual saved
                          duration may be slightly shorter because of the server
                          processing time.
        @throws CompassError If START or STOP fails.
        """
        self.start()
        time.sleep(duration_s)
        self.stop()