# Native API wake window

The API profile samples the battery before its optional network wait. It skips
that wait at or below the critical threshold. A restored low-battery latch also
skips it until a valid reading reaches the exit threshold. Missing or nonfinite
readings keep that bypass when the latch is set. An unlatched device with an
unavailable battery retains the bounded best-effort connection window.
The existing battery sample adds a 250 ms rail-settle delay and a readiness
wait of up to 3 seconds before this decision. Skipping the connection window
still runs the normal acquisition, display and protected sleep sequence.

The API profile then waits for a state subscriber before full acquisition.
`api_connection_timeout` sets the maximum wait. The default is 10 seconds.
The wait runs at boot priority 399, after sensor setup at 600 and display setup
at 400. It is asynchronous. Wi-Fi setup at priority 250 can proceed while the
wait is pending. Acquisition then runs once, on subscription or timeout.
The MQTT profile and the core acquisition/sleep sequence do not change.

The condition uses `api.connected: {state_subscription_only: true}`. A client
that requests logs alone does not release the wait. A state subscription does.
On ESPHome 2026.9.0, `APIConnectedCondition` calls
`APIServer::is_connected_with_state_subscription`, which checks the client
`state_subscription` flag. `APIConnection::on_subscribe_states_request` sets
that flag and starts the initial-state iterator when no other iterator is
active. Otherwise initial-state iteration follows the active entity-list
iterator. A subscriber can therefore receive cached sensor states too.

This is best-effort delivery. Subscription readiness does not prove that Home
Assistant has received or stored a measurement. A disconnect after readiness
does not restart acquisition or hold the device awake. A client that reconnects
before sleep can receive cached states. An offline device still completes its
normal acquisition/display/sleep cycle after the bounded wait.

The mechanism above is checked against installed ESPHome 2026.9.0 source:

- `esphome/core/base_automation.h`: asynchronous `WaitUntilAction`.
- `esphome/components/api/api_server.h`: `APIConnectedCondition`.
- `esphome/components/api/api_server.cpp`: subscription lookup.
- `esphome/components/api/api_connection.h`: subscription and initial states.

`tests/test_api_boot.py` reads the actual profile YAML, then compiles the exact
installed wait action, API condition and subscription lookup with a local
clock and fake client. It checks early/late subscription, a logs-only client,
no Home Assistant connection, and disconnect after readiness. Run the test
with ESPHome 2026.9.0 installed and `g++` available:

```bash
python3 -m unittest discover -s tests -p test_api_boot.py -v
```

The test does not open network connections. Local synthetic API/MQTT config
validation and an API firmware build add schema and compiler evidence. They
do not establish delivery on a real Home Assistant connection. Revert the
profile change to restore the previous immediate acquisition behavior.
