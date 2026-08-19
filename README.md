# SHL Home Assistant Integration

Home Assistant custom integration for Swedish hockey teams in the Swedish
Hockey League and Swedish Hockey Allsvenskan, powered by
[TheSportsDB v1](https://www.thesportsdb.com/api/spec/v1/openapi.yaml).

The integration creates one sensor for each configured team and exposes team
metadata plus upcoming and previous events as state attributes. It is intended
for Team Tracker-style dashboards and cards.

## Installation

### HACS

1. Open HACS in Home Assistant.
2. Add this repository as a custom repository of type **Integration**.
3. Install **SHL**.
4. Restart Home Assistant.

### Manual

1. Copy `custom_components/shl` into the `custom_components` directory in your
   Home Assistant configuration directory.
2. Restart Home Assistant.

The resulting path must be:

```text
config/custom_components/shl/manifest.json
```

## Configuration

Configuration is performed from **Settings -> Devices & services -> Add
Integration -> SHL**.

Enter:

- **TheSportsDB API key**: `123` is the free v1 test key. Use your own key if
  you have one.
- **SHL team names**: one or more team names, for example `HV71` and `Lulea`.

The integration searches TheSportsDB for each team name and refreshes the data
every 30 seconds.

### National teams (Landslag)

National teams such as **Tre Kronor** (search for `Sweden` or `Tre Kronor`) are
fully supported. Since national teams only compete in international competitions
(IIHF World Championship, Olympics, etc.) the *National leagues and cups only*
filter option is intentionally not available when a national team is detected.
Use **All leagues** (default) or **Specific league** to select a particular
tournament like the IIHF World Championship.

Live in-game scores are requested from TheSportsDB v2 when available. This
requires a Premium TheSportsDB API key. With the free v1 key, scheduled
upcoming and previous events continue to work, but live scores are unavailable.

## Entities

Each configured team is exposed as a sensor named like:

```text
sensor.shl_hv71_sensor
```

The sensor state is the team's points when available, or the team status/name
when points are not provided by TheSportsDB. Attributes include:

- `team`
- `team_name`
- `idTeam`
- `strLeague`
- `strSport`
- `next_events`
- `previous_events`
- `status`
- `attribution`

TheSportsDB v1 does not provide the complete standings payload used by the
retired SHL API. Standings fields such as rank, points, and goal difference may
therefore be unavailable for some teams.

## Development

Create or activate the project virtual environment, then install dependencies:

```bash
python -m pip install -r requirements_dev.txt -r requirements_test.txt
```

Run the offline test suite:

```bash
pytest -q
```

Run the opt-in live TheSportsDB test using the local `secrets.yaml` file:

```bash
RUN_SHL_LIVE_TESTS=1 pytest -q tests/test_api_live.py
```

The live test expects:

```yaml
shlapikey: 123
```

Do not commit `secrets.yaml`.

## Data source

The integration uses TheSportsDB v1 endpoints for team search and team
schedules, plus the TheSportsDB v2 live-score endpoint when a Premium API key
is configured. The free v1 key is not valid for v2 live scores.

## Brand assets

The Home Assistant integration icon and logo are based on the Swedish Hockey
League logo from [Wikimedia Commons](https://commons.wikimedia.org/wiki/File:Swedish_Hockey_League_logo.svg).

## License

See [LICENSE](LICENSE).


## Disclaimer

Live scores have not yet been tested. A premium subscription is needed from data provider.