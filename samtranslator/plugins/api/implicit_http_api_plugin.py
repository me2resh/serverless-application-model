import six

from samtranslator.model.naming import GeneratedLogicalId
from samtranslator.plugins.api.implicit_api_plugin import ImplicitApiPlugin
from samtranslator.public.open_api import OpenApiEditor
from samtranslator.public.exceptions import InvalidEventException
from samtranslator.public.sdk.resource import SamResourceType, SamResource


class ImplicitHttpApiPlugin(ImplicitApiPlugin):
    """
    This plugin provides Implicit Http API shorthand syntax in the SAM Spec.

    Implicit API syntax is just a syntactic sugar, which will be translated to AWS::Serverless::HttpApi resource.
    This is the only event source implemented as a plugin. Other event sources are not plugins because,
    DynamoDB event source, for example, is not creating the DynamoDB resource. It just adds
    a connection between the resource and Lambda. But with Implicit APIs, it creates and configures the API
    resource in addition to adding the connection. This plugin will simply tackle the resource creation bits
    and delegate the connection work to core translator.

    To sum up, here is the split of responsibilities:
    * This Plugin: Creates AWS::Serverless::HttpApi and generates OpenApi with Methods, Paths, Auth, etc,
                                            essentially anything that configures API Gateway.
    * API Event Source (In Core Translator): ONLY adds the Lambda Integration ARN to appropriate method/path
                                             in OpenApi. Does **not** configure the API by any means.
    """

    def __init__(self):
        """
        Initializes the plugin
        """
        super(ImplicitHttpApiPlugin, self).__init__(ImplicitHttpApiPlugin.__name__)

    def _setup_api_properties(self):
        """
        Sets up properties that are distinct to this plugin
        """
        self.implicit_api_logical_id = GeneratedLogicalId.implicit_http_api()
        self.implicit_api_condition = "ServerlessHttpApiCondition"
        self.api_event_type = "HttpApi"
        self.api_type = SamResourceType.HttpApi.value
        self.api_id_property = "ApiId"
        self.editor = OpenApiEditor

    def _process_api_events(self, function, api_events, template, condition=None):
        """
        Actually process given HTTP API events. Iteratively adds the APIs to OpenApi JSON in the respective
        AWS::Serverless::HttpApi resource from the template

        :param SamResource function: SAM Function containing the API events to be processed
        :param dict api_events: Http API Events extracted from the function. These events will be processed
        :param SamTemplate template: SAM Template where AWS::Serverless::HttpApi resources can be found
        :param str condition: optional; this is the condition that is on the function with the API event
        """

        for logicalId, event in api_events.items():
            # api_events only contains HttpApi events
            event_properties = event.get("Properties", {})
            if not event_properties:
                event["Properties"] = event_properties
            self._add_implicit_api_id_if_necessary(event_properties)

            api_id = self._get_api_id(event_properties)
            path = event_properties.get("Path", "")
            method = event_properties.get("Method", "")
            # If no path and method specified, add the $default path and ANY method
            if not path and not method:
                path = "$default"
                method = "x-amazon-apigateway-any-method"
                event_properties["Path"] = path
                event_properties["Method"] = method
            elif not path or not method:
                key = "Path" if not path else "Method"
                raise InvalidEventException(logicalId, "Event is missing key '{}'.".format(key))

            if not isinstance(path, six.string_types) or not isinstance(method, six.string_types):
                key = "Path" if not isinstance(path, six.string_types) else "Method"
                raise InvalidEventException(logicalId, "Api Event must have a String specified for '{}'.".format(key))

            # !Ref is resolved by this time. If it is still a dict, we can't parse/use this Api.
            if (isinstance(api_id, dict)):
                raise InvalidEventException(logicalId,
                                            "Api Event must reference an Api in the same template.")

            api_dict = self.api_conditions.setdefault(api_id, {})
            method_conditions = api_dict.setdefault(path, {})

            if condition:
                method_conditions[method] = condition

            self._add_api_to_swagger(logicalId, event_properties, template)
            api_events[logicalId] = event

        # We could have made changes to the Events structure. Write it back to function
        function.properties["Events"].update(api_events)

    def _add_implicit_api_id_if_necessary(self, event_properties):
        """
        Events for implicit APIs will *not* have the RestApiId property. Absence of this property means this event
        is associated with the AWS::Serverless::Api ImplicitAPI resource.
        This method solidifies this assumption by adding RestApiId property to events that don't have them.

        :param dict event_properties: Dictionary of event properties
        """
        if "ApiId" not in event_properties:
            event_properties["ApiId"] = {"Ref": self.implicit_api_logical_id}

    def _generate_implicit_api_resource(self):
        """
        Uses the implicit API in this file to generate an Implicit API resource
        """
        return ImplicitHttpApiResource().to_dict()

    def _get_api_definition_from_editor(self, editor):
        """
        Helper function to return the OAS definition from the editor
        """
        return editor.openapi


class ImplicitHttpApiResource(SamResource):
    """
    Returns a AWS::Serverless::HttpApi resource representing the Implicit APIs. The returned resource
    includes the empty OpenApi along with default values for other properties.
    """

    def __init__(self):
        open_api = OpenApiEditor.gen_skeleton()

        resource = {
            "Type": SamResourceType.HttpApi.value,
            "Properties": {
                "DefinitionBody": open_api,
                # Internal property that means Event source code can add Events. Used only for implicit APIs, to
                # prevent back compatibility issues for explicit APIs
                "__MANAGE_SWAGGER": True
            }
        }

        super(ImplicitHttpApiResource, self).__init__(resource)
