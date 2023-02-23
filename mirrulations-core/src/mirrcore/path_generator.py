import re

class PathGenerator:
    '''
    Gets a value from traversing a series of nested keys in a JSON object.
    default_value is the value that should be returned if any of the nested
    keys are missing from the JSON.
    '''
    def _get_nested_keys_in_json(self, json_data, nested_keys, default_value):
        json_subset = json_data

        for key in nested_keys:
            if key not in json_subset:
                return default_value
            else:
                json_subset = json_subset[key]

        return json_subset

    '''
    Returns the agency, docket id, and item id from a loaded json object.
    '''
    def _get_attributes(self, json_data, is_docket_json=False):
        item_id = self._get_nested_keys_in_json(
            json_data, ['data', 'id'], None)
        agency_id = self._get_nested_keys_in_json(
            json_data, ['data', 'attributes', 'agencyId'], None)

        if is_docket_json:
            docket_id = item_id
            item_id = None
        else:
            docket_id = self._get_nested_keys_in_json(
                json_data, ['data', 'attributes', 'docketId'], None)

            if docket_id is None:
                docket_id = parse_docket_id(item_id)
                print(f'{item_id} was parsed to get docket id: {docket_id}.')

        # convert None value to respective folder names
        if not is_docket_json and item_id is None:
            item_id = 'unknown'
        if docket_id is None:
            docket_id = 'unknown'
        if agency_id is None:
            agency_id = 'unknown'

        return agency_id, docket_id, item_id


    def parse_docket_id(self, item_id):
        segments = item_id.split('-') # list of segments separated by '-'
        segments_excluding_end = segments[:-1] # drops the last segment
        return '-'.join(segments_excluding_end)


    def get_docket_json_path(self, json): 
        agencyId, docket_id, _ = self._get_attributes(json, is_docket_json=True)

        return f'data/{agencyId}/{docket_id}/text-{docket_id}/docket/{docket_id}.json'

    
    def get_document_json_path(self, json):
        agencyId, docket_id, item_id = self._get_attributes(json)

        return f'data/{agencyId}/{docket_id}/text-{docket_id}/documents/{item_id}.json'

    def get_comment_json_path(self, json):
        agencyId, docket_id, item_id = self._get_attributes(json)

        return f'data/{agencyId}/{docket_id}/text-{docket_id}/comments/{item_id}.json'


    # def get_comment_extracted_text_path(self, json_data, file_name, extraction_method):
    #     agency, docket_id, item_id = extract_data(json_data)
    #     return self._path + f'/data/{agency}/text-{docket_id}/comments_extracted_text/{extraction_method}/{file_name}'

    # def get_document_extracted_text_path(self, json_data, file_name, extraction_method):
    #     agency, docket_id, item_id = extract_data(json_data)
    #     return self._path + f'/data/{agency}/text-{docket_id}/documents_extracted_text/{extraction_method}/{file_name}'


    # def get_document_attachment_path(self, json_data, file_name):
    #     agency, docket_id, item_id = extract_data(json_data)
    #     return self._path + f'/data/{agency}/binary-{docket_id}/documents_attachments/{file_name}'


    # def get_comment_attachment_path(self, json_data, file_name):
    #     agency, docket_id, item_id = extract_data(json_data)
    #     return self._path + f'/data/{agency}/binary-{docket_id}/comments_attachments/{file_name}'
