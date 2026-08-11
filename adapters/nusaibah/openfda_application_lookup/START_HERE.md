# START HERE — DataSpell

1. Extract `openfda_application_lookup` into:

   `E:\nusaibah_projects\demo_asset_project\pipeline_agent_v1\openfda_application_lookup`

2. In DataSpell, keep the project interpreter on the existing
   `demo_asset_project\.venv` where the PI OBS runtime is installed.

3. Open the Terminal tool window in the new folder and run:

   ```powershell
   python -m unittest discover -s tests -v
   ```

4. The package has no input binding. The business input is only:

   ```json
   {
     "application_number": "NDA020164"
   }
   ```

   `build_live_inputs.py` converts that value into the complete OBS input
   envelope, including the safe direct Runtime Source selector.

5. Do not change the adapter to add an API key, URL, `requests`, `httpx`, Core
   calls, OBS calls, storage, publication, retries, or provider response dumps.

6. After local tests pass, the next lifecycle action is to publish the adapter
   catalog/register this new asset and then use the existing governed openFDA
   Runtime Source for the recorded `local_worker` proof.
