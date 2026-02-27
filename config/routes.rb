Rails.application.routes.draw do
  root "dashboard#index"

  get "status", to: "status#index"
  resource :quick_process, only: [ :new, :create, :show ]
  resources :workflow_runs, only: [ :show ], path: "runs" do
    member do
      get :place_screws
      patch :save_screws
    end
  end

  resources :patients do
    resources :cases, except: [ :index ] do
      member do
        post :execute_workflow
      end
      resources :workflow_runs, only: [ :show ]
    end
  end

  # Health check
  get "up" => "rails/health#show", as: :rails_health_check
end
