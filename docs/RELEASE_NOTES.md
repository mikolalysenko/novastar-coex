NovaStar COEX 0.2.0 is the first public release of a local Home Assistant integration
and Python client for COEX LED controllers, hardware-tested on MX40 Pro V1.5.0.

- Control display/blackout, freeze, brightness, inputs, processing mode and presets.
- Configure color temperature and gamma; show cabinet numbers for servicing.
- Monitor controller temperature, runtime and connected cabinets.
- Set up through Home Assistant's UI; all client code is bundled for HACS.

Requires Home Assistant 2026.3.1 or newer. Install with HACS as a custom integration
repository, restart Home Assistant, then add **NovaStar COEX** under Devices & services.
Manual installers can extract `novastar_coex-v0.2.0.zip` into the HA configuration
directory. The wheel is an optional standalone Python client, not the HA integration.

Display off means blackout; it does not remove controller or cabinet power.
Close VMP before using the API. Preset application, color-temperature/gamma writes,
other controller models and multi-screen operation still need physical verification.
See the README and hardware verification matrix for the tested scope and limitations.

Default HACS catalog inclusion is a separate maintainer review. Custom-repository
installation works independently of that review.
