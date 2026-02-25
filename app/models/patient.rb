class Patient < ApplicationRecord
  has_many :cases, dependent: :destroy

  validates :name, presence: true
end
