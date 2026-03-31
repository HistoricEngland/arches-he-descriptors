define(['jquery',
    'underscore',
    'arches',
    'knockout',
    'knockout-mapping',
    'viewmodels/function',
    'bindings/chosen',
    'templates/views/components/functions/arches-he-descriptors.htm'
],
function($, _, arches, ko, koMapping, FunctionViewModel, chosen, primaryDescriptorsFunctionTemplate) {
    const viewModel = function(params) {    

        FunctionViewModel.apply(this, arguments);
        this.cards = ko.observableArray();
        this.loading = ko.observable(false);
        this.yamlConfig = ko.observable('');
        this.yamlConfigLoading = ko.observable(true);
        this.hasYamlConfig = ko.pureComputed(function() {
            var value = this.yamlConfig();
            return typeof value === 'string' && value.trim() !== '';
        }, this);
        this.cards.unshift({
            'name': null,
        });

        this.graph.cards.forEach(function(card){
            this.cards.push(card);
        }, this);

        this.name = params.config.descriptor_types.name;
        this.description = params.config.descriptor_types.description;
        this.map_popup = params.config.descriptor_types.map_popup;

        _.each([this.description, this.map_popup], function(property){
            if (property.nodegroup_id) {
                property.nodegroup_id.subscribe(function(nodegroup_id){
                    property.string_template(nodegroup_id);
                    var nodes = _.filter(this.graph.nodes, function(node){
                        return node.nodegroup_id === nodegroup_id;
                    }, this);
                    var templateFragments = [];
                    _.each(nodes, function(node){
                        templateFragments.push('<' + node.name + '>');
                    }, this);

                    var template = templateFragments.join(', ');
                    property.string_template(template);
                }, this);
            }
        }, this);

        this.loadGraphYamlConfig = function() {
            if (!this.graph || !this.graph.graphid) {
                this.yamlConfig('');
                this.yamlConfigLoading(false);
                return;
            }

            this.yamlConfigLoading(true);
            $.ajax({
                type: 'GET',
                url: '/api/display-descriptor/config/' + this.graph.graphid + '/',
                context: this,
                success: function(response) {
                    if (response && response.configured === true && response.yaml_config) {
                        this.yamlConfig(response.yaml_config);
                    } else {
                        this.yamlConfig('');
                    }
                },
                error: function() {
                    this.yamlConfig('');
                },
                complete: function() {
                    this.yamlConfigLoading(false);
                }
            });
        };

        this.reindexdb = function(){
            this.loading(true);
            $.ajax({
                type: "POST",
                url: arches.urls.reindex,
                context: this,
                data: JSON.stringify({'graphids': [this.graph.graphid]}),
                error: function() {
                    console.log('error');
                },
                complete: function(){
                    this.loading(false);
                }
            });
        };

        this.loadGraphYamlConfig();
        window.setTimeout(function(){$("select[data-bind^=chosen]").trigger("chosen:updated");}, 300);
    };

    return ko.components.register('views/components/functions/arches-he-descriptors', {
        viewModel: viewModel,
        template: primaryDescriptorsFunctionTemplate,
    });

});
