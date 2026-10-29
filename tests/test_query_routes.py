import app


def test_table_queries_are_registered_with_their_models():
    routes = {route.path: route for route in app.queries.service_spec().routes}
    assert routes['/queries/sources'].model == 'sources'
    assert routes['/queries/versions'].model == 'skill_versions'
    assert routes['/queries/semantic'].model == 'skill_versions'
    assert all(route.route_type == 'query' and route.query.startswith('app.read_') for route in routes.values())
    assert routes['/queries/semantic'].inputs == ['query', 'version_ids', 'skill_ids']
