docker/
├── app/                    # Application Layer – Use Cases & Orchestrierung
│   ├── main.py
│   ├── plugin_invoke.py
│   ├── rag.py
│   ├── rag_api.py
│   ├── registry.py
│   ├── workflow_registry.py
│   └── __init__.py
│
├── domain/                 # Domain Layer – Kernlogik & Entities
│   ├── agent.py
│   ├── identity.py
│   ├── http_identity.py
│   ├── admin_setup.py
│   └── __init__.py
│
├── infrastructure/         # Infrastructure Layer – DB, Auth, Cronjobs, Crypto
│   ├── db/
│   │   ├── db.py
│   │   ├── table.py
│   │   └── migrations/
│   ├── auth.py
│   ├── user_secrets_api.py
│   ├── secret_otp_bundle.py
│   ├── cron.py
│   ├── crypto_secrets.py
│   └── __init__.py
│
├── core/                   # Gemeinsame Basisklassen / Config / Utilities
│   └── config.py
│
├── tools/                  # Erweiterbare Tools – bleiben auf Root für schnelle Erweiterung
│   ├── agent/
│   │   ├── core/
│   │   │   ├── environment_snapshot.py
│   │   │   ├── __init__.py
│   │   │   ├── secrets/
│   │   │   │   ├── register_secrets.py
│   │   │   │   └── secrets_help.py
│   │   │   ├── tool_factory/
│   │   │   │   ├── create_tool.py
│   │   │   │   ├── __init__.py
│   │   │   │   ├── list_tools.py
│   │   │   │   ├── read_tool.py
│   │   │   │   ├── rename_tool.py
│   │   │   │   ├── replace_tool.py
│   │   │   │   ├── _tool_factory_common.py
│   │   │   │   └── update_tool.py
│   │   │   ├── tool_help/tool_help.py
│   │   │   └── workspace/workspace.py
│   │   ├── domains/
│   │   │   ├── fishing/
│   │   │   │   ├── bait_selector.py
│   │   │   │   ├── bite_index.py
│   │   │   │   ├── README.md
│   │   │   │   └── spot_recommendation.py
│   │   │   ├── gaming/
│   │   │   ├── hunting/
│   │   │   │   ├── tracking.py
│   │   │   │   └── wind_analysis.py
│   │   │   ├── README.md
│   │   │   ├── survival/
│   │   │   │   ├── risk_assessment.py
│   │   │   │   ├── shelter_guide.py
│   │   │   │   └── water_calc.py
│   │   │   └── work/shift_calendar.py
│   │   ├── external/
│   │   │   ├── browser_automation/
│   │   │   ├── github/github.py
│   │   │   ├── image_generator/
│   │   │   │   ├── image2image_realvision.py
│   │   │   │   ├── inpainting_realvision.py
│   │   │   │   ├── README.md
│   │   │   │   ├── text2image_pixelassets.py
│   │   │   │   └── text2image_realvision.py
│   │   │   ├── openweather/
│   │   │   │   ├── environment_snapshot.py
│   │   │   │   └── openweather.py
│   │   │   └── web_search/web_search.py
│   │   ├── knowledge/
│   │   │   ├── kb/kb.py
│   │   │   └── rag/rag.py
│   │   └── productivity/
│   │       ├── calendar/calendar_ics.py
│   │       ├── clocks/clock.py
│   │       ├── gmail/gmail.py
│   │       └── todos/todos.py
│   ├── __init__.py
│   ├── README.md
│   └── workflow/
│
├── workflows/              # Workflows / Use Cases – bleiben auf Root
│   ├── core/
│   ├── domains/
│   ├── external/
│   │   └── image_generator/
│   │       ├── asset_generation.py
│   │       └── inpainting_realvision.json
│   ├── game/lore_generator.py
│   ├── knowledge/
│   └── productivity/
│       ├── rss/
│       │   ├── daily_rss_summary.py
│       │   └── output/
│       └── server/monitoring.py
│
├── interfaces/             # Entry Points / Schnittstellen
│   ├── discord/
│   │   ├── bot.py
│   │   ├── client.py
│   │   └── tts.py
│   ├── email/
│   │   ├── bot.py
│   │   ├── client.py
│   │   └── tts.py
│   └── telegram/
│       ├── bot.py
│       ├── client.py
│       └── tts.py
│
├── extra_tools/
│   ├── README.md
│   └── sample_echo.py
├── compose.yaml
├── control-panel/
│   ├── agents.html
│   ├── dashboard.html
│   ├── index.html
│   ├── interface.html
│   ├── js/
│   │   ├── auth.js
│   │   └── layout.js
│   ├── layout.html
│   ├── login.html
│   ├── tools.html
│   ├── users.html
│   └── workflows.html
├── Dockerfile
├── requirements.txt
├── start.sh
└── workspace/