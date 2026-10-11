# Frozen Stage 6 baseline report

Internal Generation Yield, Emitted Candidate Validity, and Final Recommendation Coverage use the shared metric contract.

## BL-01-rule-based

```json
{
  "stochastic": false,
  "per_seed": [
    {
      "seed": 41,
      "profiles": 364,
      "internal_attempt_count": 364,
      "emitted_candidate_count": 364,
      "valid_emitted_candidate_count": 333,
      "requests_with_valid_final_plan": 333,
      "internal_generation_yield": 1.0,
      "emitted_candidate_validity": 0.9148351648351648,
      "final_recommendation_coverage": 0.9148351648351648,
      "no_plan_rate": 0.0851648351648352
    },
    {
      "seed": 42,
      "profiles": 364,
      "internal_attempt_count": 364,
      "emitted_candidate_count": 364,
      "valid_emitted_candidate_count": 333,
      "requests_with_valid_final_plan": 333,
      "internal_generation_yield": 1.0,
      "emitted_candidate_validity": 0.9148351648351648,
      "final_recommendation_coverage": 0.9148351648351648,
      "no_plan_rate": 0.0851648351648352
    },
    {
      "seed": 43,
      "profiles": 364,
      "internal_attempt_count": 364,
      "emitted_candidate_count": 364,
      "valid_emitted_candidate_count": 333,
      "requests_with_valid_final_plan": 333,
      "internal_generation_yield": 1.0,
      "emitted_candidate_validity": 0.9148351648351648,
      "final_recommendation_coverage": 0.9148351648351648,
      "no_plan_rate": 0.0851648351648352
    },
    {
      "seed": 44,
      "profiles": 364,
      "internal_attempt_count": 364,
      "emitted_candidate_count": 364,
      "valid_emitted_candidate_count": 333,
      "requests_with_valid_final_plan": 333,
      "internal_generation_yield": 1.0,
      "emitted_candidate_validity": 0.9148351648351648,
      "final_recommendation_coverage": 0.9148351648351648,
      "no_plan_rate": 0.0851648351648352
    },
    {
      "seed": 45,
      "profiles": 364,
      "internal_attempt_count": 364,
      "emitted_candidate_count": 364,
      "valid_emitted_candidate_count": 333,
      "requests_with_valid_final_plan": 333,
      "internal_generation_yield": 1.0,
      "emitted_candidate_validity": 0.9148351648351648,
      "final_recommendation_coverage": 0.9148351648351648,
      "no_plan_rate": 0.0851648351648352
    },
    {
      "seed": 46,
      "profiles": 364,
      "internal_attempt_count": 364,
      "emitted_candidate_count": 364,
      "valid_emitted_candidate_count": 333,
      "requests_with_valid_final_plan": 333,
      "internal_generation_yield": 1.0,
      "emitted_candidate_validity": 0.9148351648351648,
      "final_recommendation_coverage": 0.9148351648351648,
      "no_plan_rate": 0.0851648351648352
    },
    {
      "seed": 47,
      "profiles": 364,
      "internal_attempt_count": 364,
      "emitted_candidate_count": 364,
      "valid_emitted_candidate_count": 333,
      "requests_with_valid_final_plan": 333,
      "internal_generation_yield": 1.0,
      "emitted_candidate_validity": 0.9148351648351648,
      "final_recommendation_coverage": 0.9148351648351648,
      "no_plan_rate": 0.0851648351648352
    },
    {
      "seed": 48,
      "profiles": 364,
      "internal_attempt_count": 364,
      "emitted_candidate_count": 364,
      "valid_emitted_candidate_count": 333,
      "requests_with_valid_final_plan": 333,
      "internal_generation_yield": 1.0,
      "emitted_candidate_validity": 0.9148351648351648,
      "final_recommendation_coverage": 0.9148351648351648,
      "no_plan_rate": 0.0851648351648352
    },
    {
      "seed": 49,
      "profiles": 364,
      "internal_attempt_count": 364,
      "emitted_candidate_count": 364,
      "valid_emitted_candidate_count": 333,
      "requests_with_valid_final_plan": 333,
      "internal_generation_yield": 1.0,
      "emitted_candidate_validity": 0.9148351648351648,
      "final_recommendation_coverage": 0.9148351648351648,
      "no_plan_rate": 0.0851648351648352
    },
    {
      "seed": 50,
      "profiles": 364,
      "internal_attempt_count": 364,
      "emitted_candidate_count": 364,
      "valid_emitted_candidate_count": 333,
      "requests_with_valid_final_plan": 333,
      "internal_generation_yield": 1.0,
      "emitted_candidate_validity": 0.9148351648351648,
      "final_recommendation_coverage": 0.9148351648351648,
      "no_plan_rate": 0.0851648351648352
    }
  ],
  "internal_generation_yield": {
    "mean": 1.0,
    "sd": null,
    "n_seeds": 1,
    "ci95_half_width": null,
    "note": "deterministic_method; CI not applicable"
  },
  "emitted_candidate_validity": {
    "mean": 0.914835,
    "sd": null,
    "n_seeds": 1,
    "ci95_half_width": null,
    "note": "deterministic_method; CI not applicable"
  },
  "final_recommendation_coverage": {
    "mean": 0.914835,
    "sd": null,
    "n_seeds": 1,
    "ci95_half_width": null,
    "note": "deterministic_method; CI not applicable"
  },
  "no_plan_rate": {
    "mean": 0.085165,
    "sd": null,
    "n_seeds": 1,
    "ci95_half_width": null,
    "note": "deterministic_method; CI not applicable"
  },
  "violations_by_rule": {
    "prerequisite": 0,
    "corequisite": 0,
    "curriculum_membership": 0,
    "semester_offering": 0,
    "elective_quota": 0,
    "credit_limit": 830
  },
  "mean_latency_seconds": 1.243044,
  "over_timeout_candidate_count": 0,
  "mean_pairwise_diversity": null,
  "evidence_coverage": 1.0
}
```

## BL-02-greedy

```json
{
  "stochastic": false,
  "per_seed": [
    {
      "seed": 41,
      "profiles": 364,
      "internal_attempt_count": 364,
      "emitted_candidate_count": 364,
      "valid_emitted_candidate_count": 333,
      "requests_with_valid_final_plan": 333,
      "internal_generation_yield": 1.0,
      "emitted_candidate_validity": 0.9148351648351648,
      "final_recommendation_coverage": 0.9148351648351648,
      "no_plan_rate": 0.0851648351648352
    },
    {
      "seed": 42,
      "profiles": 364,
      "internal_attempt_count": 364,
      "emitted_candidate_count": 364,
      "valid_emitted_candidate_count": 333,
      "requests_with_valid_final_plan": 333,
      "internal_generation_yield": 1.0,
      "emitted_candidate_validity": 0.9148351648351648,
      "final_recommendation_coverage": 0.9148351648351648,
      "no_plan_rate": 0.0851648351648352
    },
    {
      "seed": 43,
      "profiles": 364,
      "internal_attempt_count": 364,
      "emitted_candidate_count": 364,
      "valid_emitted_candidate_count": 333,
      "requests_with_valid_final_plan": 333,
      "internal_generation_yield": 1.0,
      "emitted_candidate_validity": 0.9148351648351648,
      "final_recommendation_coverage": 0.9148351648351648,
      "no_plan_rate": 0.0851648351648352
    },
    {
      "seed": 44,
      "profiles": 364,
      "internal_attempt_count": 364,
      "emitted_candidate_count": 364,
      "valid_emitted_candidate_count": 333,
      "requests_with_valid_final_plan": 333,
      "internal_generation_yield": 1.0,
      "emitted_candidate_validity": 0.9148351648351648,
      "final_recommendation_coverage": 0.9148351648351648,
      "no_plan_rate": 0.0851648351648352
    },
    {
      "seed": 45,
      "profiles": 364,
      "internal_attempt_count": 364,
      "emitted_candidate_count": 364,
      "valid_emitted_candidate_count": 333,
      "requests_with_valid_final_plan": 333,
      "internal_generation_yield": 1.0,
      "emitted_candidate_validity": 0.9148351648351648,
      "final_recommendation_coverage": 0.9148351648351648,
      "no_plan_rate": 0.0851648351648352
    },
    {
      "seed": 46,
      "profiles": 364,
      "internal_attempt_count": 364,
      "emitted_candidate_count": 364,
      "valid_emitted_candidate_count": 333,
      "requests_with_valid_final_plan": 333,
      "internal_generation_yield": 1.0,
      "emitted_candidate_validity": 0.9148351648351648,
      "final_recommendation_coverage": 0.9148351648351648,
      "no_plan_rate": 0.0851648351648352
    },
    {
      "seed": 47,
      "profiles": 364,
      "internal_attempt_count": 364,
      "emitted_candidate_count": 364,
      "valid_emitted_candidate_count": 333,
      "requests_with_valid_final_plan": 333,
      "internal_generation_yield": 1.0,
      "emitted_candidate_validity": 0.9148351648351648,
      "final_recommendation_coverage": 0.9148351648351648,
      "no_plan_rate": 0.0851648351648352
    },
    {
      "seed": 48,
      "profiles": 364,
      "internal_attempt_count": 364,
      "emitted_candidate_count": 364,
      "valid_emitted_candidate_count": 333,
      "requests_with_valid_final_plan": 333,
      "internal_generation_yield": 1.0,
      "emitted_candidate_validity": 0.9148351648351648,
      "final_recommendation_coverage": 0.9148351648351648,
      "no_plan_rate": 0.0851648351648352
    },
    {
      "seed": 49,
      "profiles": 364,
      "internal_attempt_count": 364,
      "emitted_candidate_count": 364,
      "valid_emitted_candidate_count": 333,
      "requests_with_valid_final_plan": 333,
      "internal_generation_yield": 1.0,
      "emitted_candidate_validity": 0.9148351648351648,
      "final_recommendation_coverage": 0.9148351648351648,
      "no_plan_rate": 0.0851648351648352
    },
    {
      "seed": 50,
      "profiles": 364,
      "internal_attempt_count": 364,
      "emitted_candidate_count": 364,
      "valid_emitted_candidate_count": 333,
      "requests_with_valid_final_plan": 333,
      "internal_generation_yield": 1.0,
      "emitted_candidate_validity": 0.9148351648351648,
      "final_recommendation_coverage": 0.9148351648351648,
      "no_plan_rate": 0.0851648351648352
    }
  ],
  "internal_generation_yield": {
    "mean": 1.0,
    "sd": null,
    "n_seeds": 1,
    "ci95_half_width": null,
    "note": "deterministic_method; CI not applicable"
  },
  "emitted_candidate_validity": {
    "mean": 0.914835,
    "sd": null,
    "n_seeds": 1,
    "ci95_half_width": null,
    "note": "deterministic_method; CI not applicable"
  },
  "final_recommendation_coverage": {
    "mean": 0.914835,
    "sd": null,
    "n_seeds": 1,
    "ci95_half_width": null,
    "note": "deterministic_method; CI not applicable"
  },
  "no_plan_rate": {
    "mean": 0.085165,
    "sd": null,
    "n_seeds": 1,
    "ci95_half_width": null,
    "note": "deterministic_method; CI not applicable"
  },
  "violations_by_rule": {
    "prerequisite": 0,
    "corequisite": 0,
    "curriculum_membership": 0,
    "semester_offering": 0,
    "elective_quota": 0,
    "credit_limit": 830
  },
  "mean_latency_seconds": 0.918987,
  "over_timeout_candidate_count": 0,
  "mean_pairwise_diversity": null,
  "evidence_coverage": 1.0
}
```

## BL-03-beam-search

```json
{
  "stochastic": true,
  "per_seed": [
    {
      "seed": 41,
      "profiles": 364,
      "internal_attempt_count": 364,
      "emitted_candidate_count": 364,
      "valid_emitted_candidate_count": 333,
      "requests_with_valid_final_plan": 333,
      "internal_generation_yield": 1.0,
      "emitted_candidate_validity": 0.9148351648351648,
      "final_recommendation_coverage": 0.9148351648351648,
      "no_plan_rate": 0.0851648351648352
    },
    {
      "seed": 42,
      "profiles": 364,
      "internal_attempt_count": 364,
      "emitted_candidate_count": 364,
      "valid_emitted_candidate_count": 333,
      "requests_with_valid_final_plan": 333,
      "internal_generation_yield": 1.0,
      "emitted_candidate_validity": 0.9148351648351648,
      "final_recommendation_coverage": 0.9148351648351648,
      "no_plan_rate": 0.0851648351648352
    },
    {
      "seed": 43,
      "profiles": 364,
      "internal_attempt_count": 364,
      "emitted_candidate_count": 364,
      "valid_emitted_candidate_count": 333,
      "requests_with_valid_final_plan": 333,
      "internal_generation_yield": 1.0,
      "emitted_candidate_validity": 0.9148351648351648,
      "final_recommendation_coverage": 0.9148351648351648,
      "no_plan_rate": 0.0851648351648352
    },
    {
      "seed": 44,
      "profiles": 364,
      "internal_attempt_count": 364,
      "emitted_candidate_count": 364,
      "valid_emitted_candidate_count": 333,
      "requests_with_valid_final_plan": 333,
      "internal_generation_yield": 1.0,
      "emitted_candidate_validity": 0.9148351648351648,
      "final_recommendation_coverage": 0.9148351648351648,
      "no_plan_rate": 0.0851648351648352
    },
    {
      "seed": 45,
      "profiles": 364,
      "internal_attempt_count": 364,
      "emitted_candidate_count": 364,
      "valid_emitted_candidate_count": 333,
      "requests_with_valid_final_plan": 333,
      "internal_generation_yield": 1.0,
      "emitted_candidate_validity": 0.9148351648351648,
      "final_recommendation_coverage": 0.9148351648351648,
      "no_plan_rate": 0.0851648351648352
    },
    {
      "seed": 46,
      "profiles": 364,
      "internal_attempt_count": 364,
      "emitted_candidate_count": 364,
      "valid_emitted_candidate_count": 333,
      "requests_with_valid_final_plan": 333,
      "internal_generation_yield": 1.0,
      "emitted_candidate_validity": 0.9148351648351648,
      "final_recommendation_coverage": 0.9148351648351648,
      "no_plan_rate": 0.0851648351648352
    },
    {
      "seed": 47,
      "profiles": 364,
      "internal_attempt_count": 364,
      "emitted_candidate_count": 364,
      "valid_emitted_candidate_count": 333,
      "requests_with_valid_final_plan": 333,
      "internal_generation_yield": 1.0,
      "emitted_candidate_validity": 0.9148351648351648,
      "final_recommendation_coverage": 0.9148351648351648,
      "no_plan_rate": 0.0851648351648352
    },
    {
      "seed": 48,
      "profiles": 364,
      "internal_attempt_count": 364,
      "emitted_candidate_count": 364,
      "valid_emitted_candidate_count": 333,
      "requests_with_valid_final_plan": 333,
      "internal_generation_yield": 1.0,
      "emitted_candidate_validity": 0.9148351648351648,
      "final_recommendation_coverage": 0.9148351648351648,
      "no_plan_rate": 0.0851648351648352
    },
    {
      "seed": 49,
      "profiles": 364,
      "internal_attempt_count": 364,
      "emitted_candidate_count": 364,
      "valid_emitted_candidate_count": 333,
      "requests_with_valid_final_plan": 333,
      "internal_generation_yield": 1.0,
      "emitted_candidate_validity": 0.9148351648351648,
      "final_recommendation_coverage": 0.9148351648351648,
      "no_plan_rate": 0.0851648351648352
    },
    {
      "seed": 50,
      "profiles": 364,
      "internal_attempt_count": 364,
      "emitted_candidate_count": 364,
      "valid_emitted_candidate_count": 333,
      "requests_with_valid_final_plan": 333,
      "internal_generation_yield": 1.0,
      "emitted_candidate_validity": 0.9148351648351648,
      "final_recommendation_coverage": 0.9148351648351648,
      "no_plan_rate": 0.0851648351648352
    }
  ],
  "internal_generation_yield": {
    "mean": 1.0,
    "sd": 0.0,
    "n_seeds": 10,
    "ci95_half_width": 0.0
  },
  "emitted_candidate_validity": {
    "mean": 0.914835,
    "sd": 0.0,
    "n_seeds": 10,
    "ci95_half_width": 0.0
  },
  "final_recommendation_coverage": {
    "mean": 0.914835,
    "sd": 0.0,
    "n_seeds": 10,
    "ci95_half_width": 0.0
  },
  "no_plan_rate": {
    "mean": 0.085165,
    "sd": 0.0,
    "n_seeds": 10,
    "ci95_half_width": 0.0
  },
  "violations_by_rule": {
    "prerequisite": 0,
    "corequisite": 0,
    "curriculum_membership": 0,
    "semester_offering": 0,
    "elective_quota": 0,
    "credit_limit": 830
  },
  "mean_latency_seconds": 1.060413,
  "over_timeout_candidate_count": 1,
  "mean_pairwise_diversity": null,
  "evidence_coverage": 1.0
}
```

## BL-04-agent-without-ontology

```json
{
  "stochastic": true,
  "per_seed": [
    {
      "seed": 41,
      "profiles": 364,
      "internal_attempt_count": 1092,
      "emitted_candidate_count": 1092,
      "valid_emitted_candidate_count": 4,
      "requests_with_valid_final_plan": 4,
      "internal_generation_yield": 1.0,
      "emitted_candidate_validity": 0.003663003663003663,
      "final_recommendation_coverage": 0.01098901098901099,
      "no_plan_rate": 0.989010989010989
    },
    {
      "seed": 42,
      "profiles": 364,
      "internal_attempt_count": 1092,
      "emitted_candidate_count": 1092,
      "valid_emitted_candidate_count": 3,
      "requests_with_valid_final_plan": 3,
      "internal_generation_yield": 1.0,
      "emitted_candidate_validity": 0.0027472527472527475,
      "final_recommendation_coverage": 0.008241758241758242,
      "no_plan_rate": 0.9917582417582418
    },
    {
      "seed": 43,
      "profiles": 364,
      "internal_attempt_count": 1092,
      "emitted_candidate_count": 1092,
      "valid_emitted_candidate_count": 7,
      "requests_with_valid_final_plan": 7,
      "internal_generation_yield": 1.0,
      "emitted_candidate_validity": 0.00641025641025641,
      "final_recommendation_coverage": 0.019230769230769232,
      "no_plan_rate": 0.9807692307692307
    },
    {
      "seed": 44,
      "profiles": 364,
      "internal_attempt_count": 1092,
      "emitted_candidate_count": 1092,
      "valid_emitted_candidate_count": 5,
      "requests_with_valid_final_plan": 5,
      "internal_generation_yield": 1.0,
      "emitted_candidate_validity": 0.004578754578754579,
      "final_recommendation_coverage": 0.013736263736263736,
      "no_plan_rate": 0.9862637362637363
    },
    {
      "seed": 45,
      "profiles": 364,
      "internal_attempt_count": 1092,
      "emitted_candidate_count": 1092,
      "valid_emitted_candidate_count": 4,
      "requests_with_valid_final_plan": 4,
      "internal_generation_yield": 1.0,
      "emitted_candidate_validity": 0.003663003663003663,
      "final_recommendation_coverage": 0.01098901098901099,
      "no_plan_rate": 0.989010989010989
    },
    {
      "seed": 46,
      "profiles": 364,
      "internal_attempt_count": 1092,
      "emitted_candidate_count": 1092,
      "valid_emitted_candidate_count": 5,
      "requests_with_valid_final_plan": 5,
      "internal_generation_yield": 1.0,
      "emitted_candidate_validity": 0.004578754578754579,
      "final_recommendation_coverage": 0.013736263736263736,
      "no_plan_rate": 0.9862637362637363
    },
    {
      "seed": 47,
      "profiles": 364,
      "internal_attempt_count": 1092,
      "emitted_candidate_count": 1092,
      "valid_emitted_candidate_count": 1,
      "requests_with_valid_final_plan": 1,
      "internal_generation_yield": 1.0,
      "emitted_candidate_validity": 0.0009157509157509158,
      "final_recommendation_coverage": 0.0027472527472527475,
      "no_plan_rate": 0.9972527472527473
    },
    {
      "seed": 48,
      "profiles": 364,
      "internal_attempt_count": 1092,
      "emitted_candidate_count": 1092,
      "valid_emitted_candidate_count": 4,
      "requests_with_valid_final_plan": 4,
      "internal_generation_yield": 1.0,
      "emitted_candidate_validity": 0.003663003663003663,
      "final_recommendation_coverage": 0.01098901098901099,
      "no_plan_rate": 0.989010989010989
    },
    {
      "seed": 49,
      "profiles": 364,
      "internal_attempt_count": 1092,
      "emitted_candidate_count": 1092,
      "valid_emitted_candidate_count": 4,
      "requests_with_valid_final_plan": 4,
      "internal_generation_yield": 1.0,
      "emitted_candidate_validity": 0.003663003663003663,
      "final_recommendation_coverage": 0.01098901098901099,
      "no_plan_rate": 0.989010989010989
    },
    {
      "seed": 50,
      "profiles": 364,
      "internal_attempt_count": 1092,
      "emitted_candidate_count": 1092,
      "valid_emitted_candidate_count": 4,
      "requests_with_valid_final_plan": 4,
      "internal_generation_yield": 1.0,
      "emitted_candidate_validity": 0.003663003663003663,
      "final_recommendation_coverage": 0.01098901098901099,
      "no_plan_rate": 0.989010989010989
    }
  ],
  "internal_generation_yield": {
    "mean": 1.0,
    "sd": 0.0,
    "n_seeds": 10,
    "ci95_half_width": 0.0
  },
  "emitted_candidate_validity": {
    "mean": 0.003755,
    "sd": 0.001395,
    "n_seeds": 10,
    "ci95_half_width": 0.000865
  },
  "final_recommendation_coverage": {
    "mean": 0.011264,
    "sd": 0.004186,
    "n_seeds": 10,
    "ci95_half_width": 0.002595
  },
  "no_plan_rate": {
    "mean": 0.988736,
    "sd": 0.004186,
    "n_seeds": 10,
    "ci95_half_width": 0.002595
  },
  "violations_by_rule": {
    "prerequisite": 13479,
    "corequisite": 4648,
    "curriculum_membership": 21862,
    "semester_offering": 0,
    "elective_quota": 22307,
    "credit_limit": 0
  },
  "mean_latency_seconds": 12.229679,
  "over_timeout_candidate_count": 12,
  "mean_pairwise_diversity": null,
  "evidence_coverage": 1.0
}
```

## BL-05-agent-with-ontology

```json
{
  "stochastic": true,
  "per_seed": [
    {
      "seed": 41,
      "profiles": 364,
      "internal_attempt_count": 1092,
      "emitted_candidate_count": 903,
      "valid_emitted_candidate_count": 832,
      "requests_with_valid_final_plan": 333,
      "internal_generation_yield": 0.8269230769230769,
      "emitted_candidate_validity": 0.9213732004429679,
      "final_recommendation_coverage": 0.9148351648351648,
      "no_plan_rate": 0.0851648351648352
    },
    {
      "seed": 42,
      "profiles": 364,
      "internal_attempt_count": 1092,
      "emitted_candidate_count": 707,
      "valid_emitted_candidate_count": 656,
      "requests_with_valid_final_plan": 333,
      "internal_generation_yield": 0.6474358974358975,
      "emitted_candidate_validity": 0.9278642149929278,
      "final_recommendation_coverage": 0.9148351648351648,
      "no_plan_rate": 0.0851648351648352
    },
    {
      "seed": 43,
      "profiles": 364,
      "internal_attempt_count": 1092,
      "emitted_candidate_count": 687,
      "valid_emitted_candidate_count": 637,
      "requests_with_valid_final_plan": 333,
      "internal_generation_yield": 0.6291208791208791,
      "emitted_candidate_validity": 0.9272197962154294,
      "final_recommendation_coverage": 0.9148351648351648,
      "no_plan_rate": 0.0851648351648352
    },
    {
      "seed": 44,
      "profiles": 364,
      "internal_attempt_count": 1092,
      "emitted_candidate_count": 689,
      "valid_emitted_candidate_count": 638,
      "requests_with_valid_final_plan": 333,
      "internal_generation_yield": 0.6309523809523809,
      "emitted_candidate_validity": 0.9259796806966618,
      "final_recommendation_coverage": 0.9148351648351648,
      "no_plan_rate": 0.0851648351648352
    },
    {
      "seed": 45,
      "profiles": 364,
      "internal_attempt_count": 1092,
      "emitted_candidate_count": 767,
      "valid_emitted_candidate_count": 714,
      "requests_with_valid_final_plan": 333,
      "internal_generation_yield": 0.7023809523809523,
      "emitted_candidate_validity": 0.9308996088657105,
      "final_recommendation_coverage": 0.9148351648351648,
      "no_plan_rate": 0.0851648351648352
    },
    {
      "seed": 46,
      "profiles": 364,
      "internal_attempt_count": 1092,
      "emitted_candidate_count": 550,
      "valid_emitted_candidate_count": 513,
      "requests_with_valid_final_plan": 333,
      "internal_generation_yield": 0.5036630036630036,
      "emitted_candidate_validity": 0.9327272727272727,
      "final_recommendation_coverage": 0.9148351648351648,
      "no_plan_rate": 0.0851648351648352
    },
    {
      "seed": 47,
      "profiles": 364,
      "internal_attempt_count": 1086,
      "emitted_candidate_count": 709,
      "valid_emitted_candidate_count": 656,
      "requests_with_valid_final_plan": 331,
      "internal_generation_yield": 0.6528545119705341,
      "emitted_candidate_validity": 0.92524682651622,
      "final_recommendation_coverage": 0.9093406593406593,
      "no_plan_rate": 0.09065934065934067
    },
    {
      "seed": 48,
      "profiles": 364,
      "internal_attempt_count": 1092,
      "emitted_candidate_count": 915,
      "valid_emitted_candidate_count": 846,
      "requests_with_valid_final_plan": 333,
      "internal_generation_yield": 0.8379120879120879,
      "emitted_candidate_validity": 0.9245901639344263,
      "final_recommendation_coverage": 0.9148351648351648,
      "no_plan_rate": 0.0851648351648352
    },
    {
      "seed": 49,
      "profiles": 364,
      "internal_attempt_count": 1092,
      "emitted_candidate_count": 752,
      "valid_emitted_candidate_count": 700,
      "requests_with_valid_final_plan": 333,
      "internal_generation_yield": 0.6886446886446886,
      "emitted_candidate_validity": 0.9308510638297872,
      "final_recommendation_coverage": 0.9148351648351648,
      "no_plan_rate": 0.0851648351648352
    },
    {
      "seed": 50,
      "profiles": 364,
      "internal_attempt_count": 1092,
      "emitted_candidate_count": 720,
      "valid_emitted_candidate_count": 668,
      "requests_with_valid_final_plan": 333,
      "internal_generation_yield": 0.6593406593406593,
      "emitted_candidate_validity": 0.9277777777777778,
      "final_recommendation_coverage": 0.9148351648351648,
      "no_plan_rate": 0.0851648351648352
    }
  ],
  "internal_generation_yield": {
    "mean": 0.677923,
    "sd": 0.097393,
    "n_seeds": 10,
    "ci95_half_width": 0.060365
  },
  "emitted_candidate_validity": {
    "mean": 0.927453,
    "sd": 0.003396,
    "n_seeds": 10,
    "ci95_half_width": 0.002105
  },
  "final_recommendation_coverage": {
    "mean": 0.914286,
    "sd": 0.001738,
    "n_seeds": 10,
    "ci95_half_width": 0.001077
  },
  "no_plan_rate": {
    "mean": 0.085714,
    "sd": 0.001738,
    "n_seeds": 10,
    "ci95_half_width": 0.001077
  },
  "violations_by_rule": {
    "prerequisite": 0,
    "corequisite": 0,
    "curriculum_membership": 0,
    "semester_offering": 0,
    "elective_quota": 0,
    "credit_limit": 1500
  },
  "mean_latency_seconds": 2.406414,
  "over_timeout_candidate_count": 3,
  "mean_pairwise_diversity": 0.429867,
  "evidence_coverage": 1.0
}
```
