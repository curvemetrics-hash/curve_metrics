.PHONY: rollout-demo rollout-report spaces spaces-e2e up down test policy-test ci-alpha ci-beta ci-bad drift-alpha demo-alpha netpol-alpha all
up:           ; scripts/local-up.sh
down:         ; scripts/local-down.sh
test:         ; for m in namespace_baseline team_cloud_bindings; do (cd modules/$$m && tofu init -backend=false -input=false >/dev/null && tofu test) || exit 1; done
policy-test:  ; python3 -m pytest -q tests
ci-alpha:     ; AUTO_APPROVE=1 scripts/ci.sh local/fixtures/team-alpha-dev.tfvars
ci-beta:      ; AUTO_APPROVE=1 scripts/ci.sh local/fixtures/team-beta-prod.tfvars
ci-bad:       ; ! AUTO_APPROVE=1 scripts/ci.sh local/fixtures/bad-wildcard-admin.tfvars
drift-alpha:  ; scripts/drift_check.sh local/fixtures/team-alpha-dev.tfvars
demo-alpha:   ; scripts/demo_workload.sh team-alpha-dev
netpol-alpha: ; scripts/test_network_policy.sh team-alpha-dev
all: up test policy-test ci-alpha ci-beta ci-bad drift-alpha demo-alpha netpol-alpha
spaces:       ; python3 -m spaces.server
spaces-e2e:   ; scripts/test_spaces_e2e.sh
rollout-demo:  ; scripts/rollout_demo.sh 10
rollout-report: ; python3 -m rollout report --live
