/**
* This module implements parameter types.
*/

(function(){
    CMSParameter = function(){
    };
    
    CMSParameter.prototype = {
    };
    
    CMSParameterBasic = function(param_info, prefix, original_value){
        this.name = param_info.name;
        this.short_name = param_info.short_name;
        this.description = param_info.description;
        this.prefix = prefix;
        this.original_value = original_value;
    };
    
    CMSParameterBasic.prototype = {
        render : function(container){
            var parameter_name = this.prefix + this.short_name;
            var template = "<input type=\"text\" name=\"{{parameter_name}}\" " 
                        + "value=\"{{parameter_value}}\" />";
            template = template.replace(/{{parameter_name}}/g, parameter_name);
            template = template.replace(/{{parameter_value}}/g, 
                this.original_value == null? '' : this.original_value);
            container.html(template);
        }
    };

    CMSParameterString = CMSParameterBasic;
    CMSParameterFloat = CMSParameterBasic;
    CMSParameterInt = CMSParameterBasic;
    
    CMSParameterBoolean = function(param_info, prefix, original_value){
        this.name = param_info.name;
        this.short_name = param_info.short_name;
        this.description = param_info.description;
        this.prefix = prefix;
        this.original_value = original_value;
    };
    
    CMSParameterBoolean.prototype = {
        render : function(container){
            var parameter_name = this.prefix + this.short_name;
            var parameter_status = previous_value ? "checked" : "";
            var template = "<input type=\"checkbox\" name=\"{{parameter_name}}\" " 
                        "{{parameter_status}}/>";
            template = template.replace(/{{parameter_name}}/g, parameter_name);
            template = template.replace(/{{parameter_status}}/g, parameter_status);
            container.html(template);
        }
    };

    CMSParameterChoice = function(param_info, prefix, original_value){
        this.name = param_info.name;
        this.short_name = param_info.short_name;
        this.description = param_info.description;
        this.prefix = prefix;
        this.original_value = original_value;
        this.choices = param_info.choices;
    };

    CMSParameterChoice.prototype = {
        render: function(container){
            var parameter_name = this.prefix + this.short_name;
            var template = "<select name=\"" + parameter_name + "\">";
            for(var name in this.choices) {
                template += "<option value=\"";
                template += name + "\" ";
                if(this.original_value == name)
                    template += "selected ";
                template += ">";
                template += this.choices[name];
                template += "</option>";
            }
            template += "</select>";
            
            container.html(template);
        }
    };
    


    CMSInstantiateParameter = function(param_info, prefix, original_value) {
        return new CMSParameters[param_info.type](
            param_info,
            prefix,
            original_value);
    };
    
    CMSParameterCollection = function(param_info, prefix, original_value) {
        this.name = param_info.name;
        this.short_name = param_info.short_name;
        this.description = param_info.description;
        this.prefix = prefix;
        this.param_list_info = param_info.subparameters;
        this.values = original_value;

        this.param_list = []

        for(var item in this.param_list_info) {
            this.param_list.push(
                new CMSParameters[this.param_list_info[item].type](
                    this.param_list_info[item],
                    prefix + this.short_name + "_" + item + "_",
                    this.values === null ? null : this.values[item]));
        }
    }
    
    CMSParameterCollection.prototype = {
        render: function(container) {
            var template = "<table class=\"\" id=\"\" >";
            
            for(var item in this.param_list_info) {
                template +="<tr><td>";
                template += this.param_list_info[item].name;
                template += "</td>";
                template += "<td></td></tr>";
            }
            
            template += "</table>";
            
            var content = $(template);
            var rows = content.children("tbody").children("tr");
            for(var item in this.param_list_info) {
                var subcontainer = rows.eq(item).children("td").eq(1);
                this.param_list[item].render(subcontainer);
            }
            
            container.append(content);
            
        }
    };

    CMSParameterArray = function(param_info, prefix, original_value) {
        this.name = param_info.name;
        this.short_name = param_info.short_name;
        this.description = param_info.description;
        this.prefix = prefix;
        this.subparameter_info = param_info.subparameter;
        this.values = original_value;

        this.param_list = [];

        for(var item in this.values) {
            this.param_list.push(
                new CMSParameters[this.subparameter_info.type](
                    this.subparameter_info,
                    prefix + this.short_name + "_" + item + "_",
                    this.values === null ? null : this.values[item]));
        }
    }

    CMSParameterArray.prototype = {
            
        generate_row_template: function(index){
            var template = "<tr id=\"";
            template += this.prefix + this.short_name + "_row_" + index;
            template += "\"><td>";
            template += this.subparameter_info.name + " " + index;
            template += "</td>";
            template += "<td><input type=\"hidden\" name=\""
                + this.prefix + this.short_name + "_has_row" + 
                "\" value="+ index +"></td>";
            template += "<td><a href=\"#\" id=\"remove_element_" + 
                this.prefix + this.short_name + "_" + index + "\">Remove</a></td>";
            template += "</tr>";
            return template;
        },
        
        render: function(container) {
            var template = "<a href=\"#\" id=\"add_element_" + this.prefix + 
                this.short_name + "\">Add an element</a>";
            template += "<table class=\"\" id=\"element_table_"+ this.prefix 
                + this.short_name + "\" >";
            
            for(var item in this.param_list) {
                template += this.generate_row_template(item);
            }

            template += "</table>";
            
            var content = $(template);
            var rows = content.children("tbody").children("tr");
            for(var item in this.param_list) {
                var current_row = rows.eq(item)
                var subcontainer = current_row.children("td").eq(1);
                this.param_list[item].render(subcontainer);
                var remove_function = this.remove_element.bind(this,item);
                current_row.find("a#remove_element_" +
                    this.prefix + this.short_name + "_" + item)
                    .click(remove_function);
            }
            
            container.append(content);
            $("a#add_element_"+this.prefix+this.short_name)
                .click(this.add_element.bind(this));

            $("form").bind("reset", this.reset.bind(this));

            this.next_index = this.param_list.length;

        },
        
        add_element: function(){
            var table = $("table#element_table_" + this.prefix + this.short_name);
            table.append(this.generate_row_template(this.next_index));
            var current_row = table.children("tbody").children("tr:last");
            
            var parameter = new CMSParameters[this.subparameter_info.type](
                    this.subparameter_info,
                    this.prefix + this.short_name + "_" + this.next_index + "_",
                    null);
            parameter.render(current_row.children("td").eq(1));
            
            var remove_function = this.remove_element.bind(this,this.next_index);
            current_row.find("a#remove_element_" +
                    this.prefix + this.short_name + "_" + this.next_index)
                    .click(remove_function);
            this.next_index++;
            return false;
        },
        
        remove_element: function(index){
            $("tr#"+this.prefix+this.short_name+"_row_"+index).remove();
            return false;
        },
        
        reset: function() {
             var table = $("table#element_table_" + this.prefix + this.short_name);
             var add_link = $("a#add_element_"+this.prefix+this.short_name);
             var parent = table.parent();
             table.remove();
             add_link.remove();
             this.render(parent);
        }
    };
    
    CMSParameterTestcase = function(param_info, prefix, original_value) {
        this.name = param_info.name;
        this.short_name = param_info.short_name;
        this.description = param_info.description;
        this.prefix = prefix;
        this.subparameter_info = param_info.subparameter;
        this.default_value = param_info.default_value;
        this.values = original_value;

        this.param_list = [];

        if(TASK_TESTCASES !== undefined) {
            for(var item=0;item < TASK_TESTCASES; item++) {
                var previous_value = this.default_value;
                if(this.values !== null && item < this.values.length)
                    previous_value = this.values[item];
                this.param_list.push(
                    new CMSParameters[this.subparameter_info.type](
                        this.subparameter_info,
                        this.prefix + this.short_name + "_" + item + "_",
                        previous_value));
            }
        }
    }

    CMSParameterTestcase.prototype = {
        render: function(container) {
            var template = "<table class=\"\" id=\"element_table_" + this.prefix
            + this.short_name +  "\" >";
            
            for(var item=0;item < TASK_TESTCASES; item++) {
                template +="<tr><td>";
                template += this.subparameter_info.name + " " + item;
                template += "</td>";
                template += "<td></td>";
                template += "<td><a href=\"#\" id=\"remove_element_" + 
                    this.prefix + this.short_name + "_" + item + "\">Remove</a></td>";
                template += "</tr>";
            }
            
            template += "</table>";
            
            var content = $(template);
            var rows = content.children("tbody").children("tr");
            for(var item=0;item < TASK_TESTCASES; item++) {
                var subcontainer = rows.eq(item).children("td").eq(1);
                this.param_list[item].render(subcontainer);
            }

            container.append(content);

        }
    };
    
    CMSParameters = {
        'string': CMSParameterString,
        'float': CMSParameterFloat,
        'int': CMSParameterInt,
        'boolean': CMSParameterBoolean,
        'choice': CMSParameterChoice,
        'collection': CMSParameterCollection,
        'array': CMSParameterArray,
        'testcase': CMSParameterTestcase,
    };

})();
