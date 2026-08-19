"""Tests for the OCCP config flow, options flow, and entry migration."""

from unittest.mock import patch

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.occp.const import CONF_AUTHORIZATION_FILE, CONF_DEFAULT_ID_TAG, CONF_HOST, CONF_PORT, DOMAIN
from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

_BIND_PATH = "custom_components.occp.config_flow_handler.config_flow._try_bind_port"


async def test_user_flow_creates_entry(hass: HomeAssistant) -> None:
    """The happy path shows the form once, then creates an entry."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch(_BIND_PATH):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "0.0.0.0", CONF_PORT: 9500, CONF_DEFAULT_ID_TAG: "TAG1"},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "OCCP (0.0.0.0:9500)"
    assert result["data"] == {CONF_HOST: "0.0.0.0", CONF_PORT: 9500}
    assert result["options"] == {CONF_AUTHORIZATION_FILE: "", CONF_DEFAULT_ID_TAG: "TAG1"}
    assert result["result"].unique_id is not None


async def test_user_flow_port_in_use_recovers(hass: HomeAssistant) -> None:
    """A bind failure shows the form again with an error, and a retry then succeeds."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})

    with patch(_BIND_PATH, side_effect=OSError):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: "0.0.0.0", CONF_PORT: 9500}
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"port": "port_in_use"}

    with patch(_BIND_PATH):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: "0.0.0.0", CONF_PORT: 9500}
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_invalid_authorization_file_recovers(hass: HomeAssistant, tmp_path) -> None:
    """A bad authorization file path shows a form error instead of crashing setup later."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})

    with patch(_BIND_PATH):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "0.0.0.0", CONF_PORT: 9500, CONF_AUTHORIZATION_FILE: str(tmp_path / "missing.json")},
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_AUTHORIZATION_FILE: "invalid_authorization_file"}

    auth_file = tmp_path / "auth.json"
    auth_file.write_text('{"idTags": {}}', encoding="utf-8")
    with patch(_BIND_PATH):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "0.0.0.0", CONF_PORT: 9500, CONF_AUTHORIZATION_FILE: str(auth_file)},
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_duplicate_host_port_aborts(hass: HomeAssistant) -> None:
    """A second entry for the same host:port aborts instead of creating a duplicate."""
    existing = MockConfigEntry(
        domain=DOMAIN,
        title="OCCP (0.0.0.0:9500)",
        unique_id="existing-uuid",
        data={CONF_HOST: "0.0.0.0", CONF_PORT: 9500},
    )
    existing.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_HOST: "0.0.0.0", CONF_PORT: 9500})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_options_flow_round_trip(hass: HomeAssistant, mock_app_start_stop: None) -> None:
    """The options step is pre-filled with the entry's current values and can be changed."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="OCCP (0.0.0.0:9500)",
        unique_id="existing-uuid",
        data={CONF_HOST: "0.0.0.0", CONF_PORT: 9500},
        options={CONF_AUTHORIZATION_FILE: "", CONF_DEFAULT_ID_TAG: "OLDTAG"},
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(result["flow_id"], {CONF_DEFAULT_ID_TAG: "NEWTAG"})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_DEFAULT_ID_TAG] == "NEWTAG"


async def test_options_flow_invalid_authorization_file_recovers(
    hass: HomeAssistant, mock_app_start_stop: None, tmp_path
) -> None:
    """A bad authorization file path in the options flow shows a form error, not a later crash."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="OCCP (0.0.0.0:9500)",
        unique_id="existing-uuid",
        data={CONF_HOST: "0.0.0.0", CONF_PORT: 9500},
        options={CONF_AUTHORIZATION_FILE: "", CONF_DEFAULT_ID_TAG: "OLDTAG"},
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_AUTHORIZATION_FILE: str(tmp_path / "missing.json")}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_AUTHORIZATION_FILE: "invalid_authorization_file"}
    assert entry.options[CONF_AUTHORIZATION_FILE] == ""


async def test_migrate_entry_moves_options_out_of_data(
    hass: HomeAssistant, mock_app_start_stop: None, tmp_path
) -> None:
    """A version 1.1 entry (authorization_file/default_id_tag still in data) migrates to 1.2."""
    auth_file = tmp_path / "auth.json"
    auth_file.write_text('{"idTags": {"ABC123": {"blocked": false}}}', encoding="utf-8")

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="OCCP (0.0.0.0:9500)",
        unique_id="existing-uuid",
        data={
            CONF_HOST: "0.0.0.0",
            CONF_PORT: 9500,
            CONF_AUTHORIZATION_FILE: str(auth_file),
            CONF_DEFAULT_ID_TAG: "TAG1",
        },
        version=1,
        minor_version=1,
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.minor_version == 2
    assert entry.data == {CONF_HOST: "0.0.0.0", CONF_PORT: 9500}
    assert entry.options == {CONF_AUTHORIZATION_FILE: str(auth_file), CONF_DEFAULT_ID_TAG: "TAG1"}


async def test_setup_fails_cleanly_when_authorization_file_disappears_after_setup(
    hass: HomeAssistant, mock_app_start_stop: None, tmp_path
) -> None:
    """A file valid at options-flow time but missing at (re)setup time is a clean ConfigEntryError.

    Covers the case the flow-time validation cannot: the file is edited or
    removed after the entry was created.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="OCCP (0.0.0.0:9500)",
        unique_id="existing-uuid",
        data={CONF_HOST: "0.0.0.0", CONF_PORT: 9500},
        options={CONF_AUTHORIZATION_FILE: str(tmp_path / "gone.json"), CONF_DEFAULT_ID_TAG: "TAG1"},
    )
    entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.SETUP_ERROR
