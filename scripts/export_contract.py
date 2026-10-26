"""Export only the public read API from the Cloud application's OpenAPI schema."""
import json
from pathlib import Path

from app import application

schema=application.openapi()
schema['paths']={'/api'+path:value for path,value in schema['paths'].items() if path in {'/v1/search','/v1/catalog'}}
schema['info']['description']='Shared public search and browse contract for the website and native skill client.'
Path('contracts/search.openapi.json').write_text(json.dumps(schema,indent=2)+'\n')
