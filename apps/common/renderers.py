from rest_framework.renderers import JSONRenderer

class StandardJSONRenderer(JSONRenderer):
    def render(self, data, accepted_media_type=None, renderer_context=None):
        response = renderer_context.get('response') if renderer_context else None
        
        # If response structure is already formatted in our custom format, return it directly
        if isinstance(data, dict) and all(k in data for k in ['success', 'message', 'data', 'errors', 'meta']):
            return super().render(data, accepted_media_type, renderer_context)

        success = True
        message = "Success"
        errors = None
        meta = {}

        if response:
            if response.status_code >= 400:
                success = False
                message = getattr(response, 'custom_message', "Error occurred")
                errors = data
                data = None
            else:
                message = getattr(response, 'custom_message', "Success")

        # Handle paginated data format from DRF's standard pagination
        if isinstance(data, dict) and 'results' in data and 'count' in data:
            request = renderer_context.get('request') if renderer_context else None
            page = 1
            page_size = 10
            if request:
                try:
                    page = int(request.query_params.get('page', 1))
                except ValueError:
                    page = 1
                try:
                    page_size = int(request.query_params.get('page_size', 10))
                except ValueError:
                    page_size = 10

            meta = {
                'page': page,
                'page_size': page_size,
                'total': data.get('count', 0),
                'next': data.get('next'),
                'previous': data.get('previous')
            }
            data = data.get('results')

        formatted_data = {
            'success': success,
            'message': message,
            'data': data,
            'errors': errors,
            'meta': meta
        }
        return super().render(formatted_data, accepted_media_type, renderer_context)
