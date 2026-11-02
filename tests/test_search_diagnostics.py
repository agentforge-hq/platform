import json

import pytest

from agentforge_backend.models import SearchRequest
from evaluation.core import EvaluationError
from scripts.diagnose_search import compare_candidates, development_requests
from test_backend import fixture


def test_semantic_gate_can_remove_both_unrelated_and_potentially_useful_keyword_results():
    semantic = fixture('permission-review', 'example/review')
    useful_keyword = fixture('permission-checks', 'example/checks')
    distractor = fixture('permission-dashboard', 'example/dashboard')
    distractor.summary = 'Display permission errors in an Azure dashboard.'
    distractor.capabilities = ['Show missing role settings and permission checks.']
    distractor.example_prompts = ['Display the permission checks dashboard.']
    request = SearchRequest(query='Review missing permission checks', limit=3)
    result = compare_candidates(
        [semantic, useful_keyword, distractor],
        request,
        [{'skill_id': semantic.skill_id, 'score': 0.7}, {'skill_id': useful_keyword.skill_id, 'score': 0.61}],
    )
    assert set(result['baseline']) == {semantic.skill_id, useful_keyword.skill_id, distractor.skill_id}
    assert result['candidate'] == [semantic.skill_id]
    assert set(result['baseline_lexical_only']) == {useful_keyword.skill_id, distractor.skill_id}
    assert result['human_decision'] is None


def test_no_above_floor_semantic_match_is_not_a_successful_relevance_judgment():
    skill = fixture()
    result = compare_candidates(
        [skill],
        SearchRequest(query='Review missing permission checks'),
        [{'skill_id': skill.skill_id, 'score': 0.6}],
    )
    assert result['baseline'] == [skill.skill_id]
    assert result['candidate'] == []
    assert result['human_decision'] is None


@pytest.mark.parametrize(
    'scores',
    [
        [{'skill_id': 'example/review', 'score': float('nan')}],
        [{'skill_id': 'example/review', 'score': True}],
        [{'skill_id': 'missing', 'score': 0.7}],
        [{'skill_id': 'example/review', 'score': 0.7}, {'skill_id': 'example/review', 'score': 0.6}],
    ],
)
def test_invalid_semantic_evidence_is_refused(scores):
    with pytest.raises(EvaluationError):
        compare_candidates([fixture()], SearchRequest(query='Review permissions'), scores)


def test_an_ineligible_semantic_candidate_cannot_reenter_the_experiment():
    skill = fixture()
    skill.adoption_status = 'unavailable'
    with pytest.raises(EvaluationError):
        compare_candidates(
            [skill], SearchRequest(query='Review permissions'), [{'skill_id': skill.skill_id, 'score': 0.9}]
        )


def test_approximate_search_near_ties_keep_the_backend_rank_order():
    first = fixture('first', 'example/first')
    second = fixture('second', 'example/second')
    result = compare_candidates(
        [first, second],
        SearchRequest(query='novel vocabulary', limit=3),
        [
            {'skill_id': first.skill_id, 'score': 0.64752259605377},
            {'skill_id': second.skill_id, 'score': 0.6475505684609006},
        ],
    )
    assert result['baseline'] == result['candidate'] == [first.skill_id, second.skill_id]


def test_replay_uses_the_captured_keyword_pool_without_recomputing():
    skill = fixture()
    score = 13.815510557964275
    result = compare_candidates(
        [skill],
        SearchRequest(query='novel vocabulary'),
        [],
        lexical_scores=[{'skill_id': skill.skill_id, 'score': score}],
    )
    assert result['lexical_candidates'] == [{'skill_id': skill.skill_id, 'score': score}]
    assert result['baseline'] == [skill.skill_id]
    assert result['candidate'] == []


@pytest.mark.parametrize('count', [0, 21])
def test_development_requests_are_bounded_before_any_catalog_read(tmp_path, count):
    path = tmp_path / 'tasks.json'
    path.write_text(json.dumps({'prompts': [{'id': str(i), 'text': 'Test task'} for i in range(count)]}))
    with pytest.raises(EvaluationError, match='between one and twenty'):
        development_requests(path)


def test_repeated_task_wording_cannot_be_counted_as_separate_evidence(tmp_path):
    path = tmp_path / 'tasks.json'
    path.write_text(
        json.dumps(
            {
                'prompts': [
                    {'id': 'one', 'text': 'Inspect the invented fixture'},
                    {'id': 'two', 'text': ' Inspect the invented fixture! '},
                ]
            }
        )
    )
    with pytest.raises(EvaluationError, match='text must be distinct'):
        development_requests(path)


def test_stopword_only_tasks_cannot_acquire_a_semantic_channel_the_service_skips():
    skill = fixture()
    request = SearchRequest(query='What do I do?')
    result = compare_candidates([skill], request, [])
    assert result['baseline'] == result['candidate'] == []
    with pytest.raises(EvaluationError, match='contradict the frozen retrieval condition'):
        compare_candidates([skill], request, [{'skill_id': skill.skill_id, 'score': 0.9}])
