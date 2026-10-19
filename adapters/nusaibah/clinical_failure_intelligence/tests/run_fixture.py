"""Provider-free developer preview. No OBS/Core/provider call is made."""
import argparse
import json
from fakes import ASSET_ROOT, FakeInputs
from clinical_failure_intelligence.orchestration import run_analysis


def main():
    """Run the selected synthetic context using explicit runtime doubles."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('mechanistic_case', 'cohort_pattern', 'prepared_evidence_preflight'))
    args = parser.parse_args()
    data = json.loads((ASSET_ROOT / 'tests/fixtures' / (args.mode + '.json')).read_text())
    print(json.dumps(run_analysis(data if args.mode == 'prepared_evidence_preflight' else FakeInputs(data)), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
