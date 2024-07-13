var testUtils = require('web.test_utils');
var Widget = require('map_field.location_map');

odoo.define('map_field.tests', function (require) {
    "use strict";


    QUnit.module('Map Field Widget', {
        beforeEach: function () {
            this.widget = new Widget(null);
        },
        afterEach: function () {
            this.widget.destroy();
        },
    });

    QUnit.test('Render Map Field', function (assert) {
        assert.expect(1);

        var $target = testUtils.prepareTarget();

        this.widget.appendTo($target);

        assert.ok($target.find('.map-field').length, 'Map field is rendered');
    });

    // Add more test cases here

});