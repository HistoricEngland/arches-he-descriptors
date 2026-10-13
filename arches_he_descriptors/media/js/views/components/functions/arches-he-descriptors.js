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

        this.yamlConfigDisplayName = ko.observable('');
        this.yamlConfigDisplayDescription = ko.observable('');
        this.yamlConfigMapPopup = ko.observable('');
        this.yamlConfigLoading = ko.observable(true);

        // Alias kept for any external references
        this.yamlConfig = this.yamlConfigDisplayName;

        var self = this;
        function makeHasConfig(obs) {
            return ko.pureComputed(function() {
                var v = obs();
                return typeof v === 'string' && v.trim() !== '';
            });
        }
        this.hasYamlConfig = makeHasConfig(this.yamlConfigDisplayName);
        this.hasYamlConfigDisplayDescription = makeHasConfig(this.yamlConfigDisplayDescription);
        this.hasYamlConfigMapPopup = makeHasConfig(this.yamlConfigMapPopup);

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

        var SECTION_OBSERVABLES = [
            { descriptorType: 'display_name',        obs: this.yamlConfigDisplayName },
            { descriptorType: 'display_description', obs: this.yamlConfigDisplayDescription },
            { descriptorType: 'map_popup',           obs: this.yamlConfigMapPopup },
        ];

        this.loadGraphYamlConfig = function() {
            if (!this.graph || !this.graph.graphid) {
                SECTION_OBSERVABLES.forEach(function(s) { s.obs(''); });
                this.yamlConfigLoading(false);
                return;
            }

            this.yamlConfigLoading(true);
            var graphid = this.graph.graphid;
            var pending = SECTION_OBSERVABLES.length;

            function done() {
                pending -= 1;
                if (pending === 0) {
                    self.yamlConfigLoading(false);
                }
            }

            SECTION_OBSERVABLES.forEach(function(section) {
                $.ajax({
                    type: 'GET',
                    url: '/api/display-descriptor/config/' + graphid + '/?descriptor_type=' + section.descriptorType,
                    success: function(response) {
                        if (response && response.configured === true && response.yaml_config) {
                            section.obs(response.yaml_config);
                        } else {
                            section.obs('');
                        }
                    },
                    error: function() {
                        section.obs('');
                    },
                    complete: done,
                });
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
