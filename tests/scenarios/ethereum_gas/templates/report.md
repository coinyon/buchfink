# {{ title }}

## Events
{% for event in events %}
* [{{ get_event_type(event) }}] {{ event.to_string(str) }}
{% endfor %}
