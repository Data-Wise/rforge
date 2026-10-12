import pytest
from .test_release_ci import records
from .test_release_verifier import v


@pytest.mark.parametrize('name',['full_gates','rendered_review','adversarial_review','requirement_mapping'])
@pytest.mark.parametrize('defect',['missing','failed','stale','no-provenance'])
def test_gate_record_validation(name,defect):
    platforms,observations=records()
    if defect=='missing':observations.pop(name)
    elif defect=='failed':observations[name]['status']='failed'
    elif defect=='stale':observations[name]['candidate_sha']='old'
    else:observations[name]['provenance']=''
    with pytest.raises(v.VerificationError):v.validate_aggregate(platforms,observations,candidate_sha='sha')


def test_review_record_validation():
    platforms,observations=records()
    assert v.validate_aggregate(platforms,observations,candidate_sha='sha')['verified']
    observations['adversarial_review']['status']='findings-unresolved'
    with pytest.raises(v.VerificationError):v.validate_aggregate(platforms,observations,candidate_sha='sha')
