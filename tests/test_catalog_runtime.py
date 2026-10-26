import os
import pytest


@pytest.mark.skipif(not os.environ.get('AGENTFORGE_TEST_TARGET'),reason='A real isolated catalog is required')
def test_published_catalog_has_one_row_per_pointer():
    import app
    app.TableModel.bind_all(os.environ['AGENTFORGE_TEST_TARGET'])
    pointers=app.published_versions()
    rows=app.current_rows(pointers)
    assert pointers
    assert len(rows)==len(set(pointers))
    assert len(rows)==len({r.skill_id for r in rows})
    assert {r.skill_id+'@'+r.source.revision for r in rows}==set(pointers)
