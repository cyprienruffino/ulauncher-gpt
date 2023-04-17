import logging
from ulauncher.api.client.Extension import Extension
from ulauncher.api.client.EventListener import EventListener
from ulauncher.api.shared.event import KeywordQueryEvent, ItemEnterEvent
from ulauncher.api.shared.item.ExtensionResultItem import ExtensionResultItem
from ulauncher.api.shared.action.RenderResultListAction import RenderResultListAction
from ulauncher.api.shared.action.ExtensionCustomAction import ExtensionCustomAction
from ulauncher.api.shared.action.CopyToClipboardAction import CopyToClipboardAction
from ulauncher.api.shared.action.DoNothingAction import DoNothingAction
import requests
import json

logger = logging.getLogger(__name__)
EXTENSION_ICON = 'images/icon.png'
ENDPOINT = "https://api.openai.com/v1/chat/completions"


def query(search_term, system_prompt, api_key, temperature, max_tokens, top_p, frequency_penalty, presence_penalty, model):
    # Get search term
    logger.info('The search term is: %s', search_term)
    # Display blank prompt if user hasn't typed anything
    if not search_term:
        logger.info('Displaying blank prompt')
        return RenderResultListAction([
            ExtensionResultItem(icon=EXTENSION_ICON,
                                name='Type in a prompt...',
                                on_enter=DoNothingAction())
        ])

    # Create POST request
    headers = {
        'content-type': 'application/json',
        'Authorization': 'Bearer ' + api_key
    }

    body = {
        "messages": [
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": search_term
            }
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "top_p": top_p,
        "frequency_penalty": frequency_penalty,
        "presence_penalty": presence_penalty,
        "model": model,
    }
    body = json.dumps(body)

    logger.info('Request body: %s', str(body))
    logger.info('Request headers: %s', str(headers))

    # Send POST request
    logger.info('Sending request')
    response = requests.post(
        ENDPOINT, headers=headers, data=body, timeout=10)

    logger.info('Request succeeded')
    logger.info('Response: %s', str(response))

    return response



def wrap_text(text, max_w):
    words = text.split()
    lines = []
    current_line = ''
    for word in words:
        if len(current_line + word) <= max_w:
            current_line += ' ' + word
        else:
            lines.append(current_line.strip())
            current_line = word
    lines.append(current_line.strip())
    return '\n'.join(lines)

def create_items(response, line_wrap):
    # Get response
    # Choice schema
    #  { message: Message, finish_reason: string, index: number }
    # Message schema
    #  { role: string, content: string }
    try:
        response = response.json()
        choices = response['choices']
    except Exception as err:
        logger.error('Failed to parse response: %s', str(response))
        errMsg = "Unknown error, please check logs for more info"
        try:
            errMsg = response['error']['message']
        except Exception:
            pass

        raise Exception(str(response) + errMsg)
    items: list[ExtensionResultItem] = []
    for choice in choices:
        message = choice['message']['content']
        message = wrap_text(message, line_wrap)

        items.append(ExtensionResultItem(icon=EXTENSION_ICON, name="Assistant", description=message,
                                        on_enter=CopyToClipboardAction(message)))
    try:
        item_string = ' | '.join([item.description for item in items])
        logger.info("Results: %s", item_string)
    except Exception as err:
        logger.error('Failed to log results: %s', str(err))
        logger.error('Results: %s', str(items))

    return items


class GPTExtension(Extension):
    """
    Ulauncher extension to generate text using GPT-3
    """

    def __init__(self):
        super(GPTExtension, self).__init__()
        logger.info('GPT-3 extension started')
        self.subscribe(KeywordQueryEvent, KeywordQueryEventListener())
        self.subscribe(ItemEnterEvent, ItemEnterEventListener())


class SettingsHandler:
    def parse_prefs(self, preferences):
        logger.info('Processing user preferences')
        self.api_key = preferences['api_key']
        self.max_tokens = int(preferences['max_tokens'])
        self.frequency_penalty = float(
            preferences['frequency_penalty'])
        self.presence_penalty = float(preferences['presence_penalty'])
        self.temperature = float(preferences['temperature'])
        self.top_p = float(preferences['top_p'])
        self.system_prompt = preferences['system_prompt']
        self.line_wrap = int(preferences['line_wrap'])
        self.model = preferences['model']
        self.wait_for_enter = int(preferences['wait_before_query'])

class ItemEnterEventListener(EventListener, SettingsHandler):

    def on_event(self, event, extension):
        # Get user preferences
        try:
            self.parse_prefs(extension.preferences)
        # pylint: disable=broad-except
        except Exception as err:
            logger.error('Failed to parse preferences: %s', str(err))
            return RenderResultListAction([
                ExtensionResultItem(icon=EXTENSION_ICON,
                                    name='Failed to parse preferences: ' +
                                    str(err),
                                    on_enter=CopyToClipboardAction(str(err)))
            ])

        search_term = event.get_data()       

        try:
            response = query(
                search_term, 
                self.system_prompt, 
                self.api_key, 
                self.temperature, 
                self.max_tokens, 
                self.top_p, 
                self.frequency_penalty, 
                self.presence_penalty, 
                self.model
            )
        except Exception as err:
            logger.error('Request failed: %s', str(err))
            return RenderResultListAction([
            ExtensionResultItem(icon=EXTENSION_ICON,
                            name='Request failed: ' + str(err),
                            on_enter=CopyToClipboardAction(str(err)))
            ])

        items = create_items(response, self.line_wrap)
        return RenderResultListAction(items)
    
        
        

class KeywordQueryEventListener(EventListener, SettingsHandler):
    """
    Event listener for KeywordQueryEvent
    """

    def on_event(self, event, extension):
        # Get user preferences
        try:
            self.parse_prefs(extension.preferences)
        # pylint: disable=broad-except
        except Exception as err:
            logger.error('Failed to parse preferences: %s', str(err))
            return RenderResultListAction([
                ExtensionResultItem(icon=EXTENSION_ICON,
                                    name='Failed to parse preferences: ' +
                                    str(err),
                                    on_enter=CopyToClipboardAction(str(err)))
            ])

        search_term = str(event.get_argument())

        if self.wait_for_enter:
            return RenderResultListAction([
                ExtensionResultItem(icon=EXTENSION_ICON,
                                    name='Waiting until Enter is pressed: '
                                        + search_term,
                                    on_enter=ExtensionCustomAction(search_term, keep_app_open=True))
            ])
        else:
            try:
                response = query(
                    search_term, 
                    self.system_prompt, 
                    self.api_key, 
                    self.temperature, 
                    self.max_tokens, 
                    self.top_p, 
                    self.frequency_penalty, 
                    self.presence_penalty, 
                    self.model
                )
            except Exception as err:
                logger.error('Request failed: %s', str(err))
                return RenderResultListAction([
                ExtensionResultItem(icon=EXTENSION_ICON,
                                name='Request failed: ' + str(err),
                                on_enter=CopyToClipboardAction(str(err)))
                ])

            items = create_items(response, self.line_wrap)
            return RenderResultListAction(items)


if __name__ == '__main__':
    GPTExtension().run()
