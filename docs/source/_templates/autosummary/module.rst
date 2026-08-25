{{ fullname | escape | underline }}

.. currentmodule:: {{ fullname }}

.. automodule:: {{ fullname }}

   {% block attributes %}
   {%- if attributes %}
   .. rubric:: {{ _('Module Attributes') }}

   .. autosummary::
   {% for item in attributes if item|include_module_member %}
      {{ item }}
   {%- endfor %}
   {% endif %}
   {%- endblock %}

   {%- block functions %}
   {%- if functions %}
   .. rubric:: {{ _('Functions') }}

   .. autosummary::
      :toctree:
   {% for item in functions if item|include_module_member %}
      {{ item }}
   {%- endfor %}
   {% endif %}
   {%- endblock %}

   {%- block classes %}
   {%- if classes %}
   .. rubric:: {{ _('Classes') }}

   .. autosummary::
      :toctree:
   {% for item in classes if item|include_module_member %}
      {{ item }}
   {%- endfor %}
   {% endif %}
   {%- endblock %}

   {%- block exceptions %}
   {%- if exceptions %}
   .. rubric:: {{ _('Exceptions') }}

   .. autosummary::
      :toctree:
   {% for item in exceptions if item|include_module_member %}
      {{ item }}
   {%- endfor %}
   {% endif %}
   {%- endblock %}


{%- block modules %}
{%- if modules %}
.. rubric:: Modules

.. autosummary::
   :toctree:
   :recursive:
{% for item in modules if item|include_module_member %}
   {{ item }}
{%- endfor %}
{% endif %}
{%- endblock %}

{% block attribute_docs %}
{% if attributes %}
.. rubric:: Attributes Documentation
{% for item in attributes if item|include_module_member %}
.. autodata:: {{ item }}
{%- endfor %}
{% endif %}
{% endblock %}
