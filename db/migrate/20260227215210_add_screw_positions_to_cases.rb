class AddScrewPositionsToCases < ActiveRecord::Migration[8.1]
  def change
    add_column :cases, :screw_positions, :jsonb, default: []
  end
end
